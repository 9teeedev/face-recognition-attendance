from flask import Flask, request, jsonify
import cv2
import numpy as np
import face_recognition
import sqlite3
import threading
from flask_cors import CORS
import os
from datetime import datetime
from pprint import pprint
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.errors import HttpError
from google.auth.exceptions import TransportError
import logging
import traceback
import mysql.connector
import schedule
import time


app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ตั้งค่า Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("teeedev-43df466db92f.json", scope)
client = gspread.authorize(creds)


# Google Sheet ID (เปลี่ยนเป็นของคุณ)
SPREADSHEET_ID = "SPREADSHEET_ID"
try:
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # เปิด Sheet ตาม ID

    test_value = sheet.cell(1, 1).value  # ลองอ่านค่าจากเซลล์ A1

    print(f"✅ Connected to Google Sheet. First cell value: {test_value}")
except Exception as e:
    print(f"❌ Cannot access the sheet: {str(e)}")

# ฟังก์ชันสำหรับเชื่อมต่อ MySQL แบบไม่ระบุฐานข้อมูล (สำหรับสร้าง database)
def get_mysql_connection_without_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="1234"
    )

# ฟังก์ชันสำหรับสร้างฐานข้อมูลหากไม่มี
def create_database_if_not_exists():
    try:
        # เชื่อมต่อ MySQL โดยไม่ระบุฐานข้อมูล
        conn = get_mysql_connection_without_db()
        cursor = conn.cursor()
        
        # สร้างฐานข้อมูลหากไม่มี
        cursor.execute("CREATE DATABASE IF NOT EXISTS facedetection")
        print("✅ Database 'facedetection' created or already exists")
        
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"❌ Error creating database: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

# ฟังก์ชันสำหรับเชื่อมต่อ MySQL (เปิดใหม่ทุกครั้งที่เรียกใช้)
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="1234",
            database="facedetection"
        )
    except mysql.connector.Error as e:
        print(f"❌ Database connection error: {e}")
        # หากเชื่อมต่อไม่ได้ ลองสร้างฐานข้อมูลใหม่
        if "Unknown database" in str(e):
            print("🔄 Database not found, creating new database...")
            if create_database_if_not_exists():
                return mysql.connector.connect(
                    host="127.0.0.1",
                    user="root",
                    password="1234",
                    database="facedetection"
                )
        raise

def create_tables():
    try:
        # สร้างฐานข้อมูลก่อน
        create_database_if_not_exists()
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # คำสั่งสร้างตาราง
        tables = {
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    user_code VARCHAR(50) UNIQUE NOT NULL,
                    face_encoding LONGBLOB NOT NULL
                );
            """,
            "check_in_out": """
                CREATE TABLE IF NOT EXISTS check_in_out (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status ENUM('check-in', 'check-out') NOT NULL,
                    synced TINYINT(1) DEFAULT 0
                );
            """,
            "notifications" :""" 
                CREATE TABLE IF NOT EXISTS notifications (
                    user_id VARCHAR(255) PRIMARY KEY,
                    last_notification TIMESTAMP
                );
            """
        }

        for name, query in tables.items():
            cursor.execute(query)
            print(f"✅ Created table: {name}")
        
        conn.commit()
        print("✅ เชื่อมต่อฐานข้อมูลสำเร็จ และสร้างตารางแล้ว")
        cursor.close()
        conn.close() # ✅ ปิด connection ทันทีเมื่อใช้เสร็จ
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise

create_tables()

class FaceRecognitionSystem:
    def __init__(self):
        self.lock = threading.Lock()
        
    def recognize_faces(self, frame):
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)

            if face_locations:
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                for face_encoding in face_encodings:
                    matches = self.compare_face_with_database(face_encoding)
                    with self.lock:
                        return matches if matches else "Unknown"
            return "Unknown"
        except Exception as e:
            logger.error(f"Face recognition error: {e}")
            logger.error(traceback.format_exc())
            raise

    # ✅ ฟังก์ชันเปรียบเทียบใบหน้ากับฐานข้อมูล
    def compare_face_with_database(self, face_encoding):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # ดึงข้อมูลทั้งหมดจากฐานข้อมูล
            cursor.execute('SELECT name, user_code, face_encoding FROM users')
            database_faces = cursor.fetchall()
            
            cursor.close()
            conn.close()  # ✅ ปิด connection ทันทีเมื่อใช้เสร็จ

            for name, user_code, stored_encoding_bytes in database_faces:
                # แปลง face_encoding จาก binary (BLOB) เป็น numpy array
                stored_encoding = np.frombuffer(stored_encoding_bytes, dtype=np.float64)
                
                # เปรียบเทียบใบหน้ากับฐานข้อมูล
                match = face_recognition.compare_faces([stored_encoding], face_encoding, tolerance=0.38)

                if match[0]:
                    return name, user_code

            return None  # ถ้าไม่มีใบหน้าตรงกัน

        except Exception as e:
            logger.error(f"❌ Face comparison error: {e}")
            logger.error(traceback.format_exc())
            return None
    
    # ✅ อัปเดตเวลาแจ้งเตือนล่าสุด
    def update_notification_time(self, user_id):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                INSERT INTO notifications (user_id, last_notification) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE last_notification = VALUES(last_notification)
            """, (user_id, now))

            conn.commit()
            cursor.close()
            conn.close()  # ✅ ปิด connection ทันทีเมื่อใช้เสร็จ
            return True

        except Exception as e:
            print(f"❌ Update notification error: {e}")
            return False

    # ✅ เช็คว่าผู้ใช้ถูกแจ้งเตือนใน 1 ชั่วโมงที่ผ่านมาไหม
    def check_last_notification(self, user_id):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT last_notification FROM notifications WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()  # ✅ ปิด connection ทันทีเมื่อใช้เสร็จ

            if result:
                last_time = result[0]  # MySQL คืนค่าเป็น datetime โดยตรง
                return (datetime.now() - last_time).total_seconds() < 3600  # ✅ ตรวจสอบว่าผ่านไปยังไม่ถึง 1 ชม.
            return False

        except Exception as e:
            print(f"❌ Check notification error: {e}")
            return False

    def update_absent_users(self):
        """Update absent users in Google Sheet by replacing empty cells with 0"""
        try:
            logger.info("Starting absent users update check...")
            # ดึงข้อมูลจาก Google Sheets
            records = sheet.get_all_records()
            headers = sheet.row_values(1)

            # กำหนดคอลัมน์ที่เป็นข้อมูลวันที่ (ยกเว้น "Name" และ "User ID")
            date_columns = [col for col in headers if col not in ["Name", "User ID"]]
            
            updated = False
            # เริ่มที่แถวที่ 2 เนื่องจากแถวแรกเป็น header
            for i, row in enumerate(records, start=2):
                if not row.get("User ID"):
                    continue  # ข้ามแถวที่ไม่มี User ID

                update_needed = False
                new_row_values = []
                # วนลูปทุกคอลัมน์ใน headers
                for header in headers:
                    if header in date_columns:
                        value = row.get(header, "")
                        # ถ้าเซลล์ว่าง (หรือเป็น string ว่าง) ให้เปลี่ยนเป็น 0
                        if value == "" or value is None:
                            value = 0
                            update_needed = True
                    else:
                        value = row.get(header, "")
                    new_row_values.append(value)
                
                # ถ้าพบว่าในแถวมีเซลล์ว่าง ให้อัปเดตแถวนี้ใน Google Sheets
                if update_needed:
                    # กำหนด range ให้ครอบคลุมแถว i ทั้งหมด (A ถึงคอลัมน์สุดท้าย)
                    range_name = f"A{i}:{chr(65 + len(headers) - 1)}{i}"
                    try:
                        sheet.update(range_name, [new_row_values])
                        logger.info(f"Updated row {i} with values: {new_row_values}")
                        updated = True
                    except Exception as sheet_error:
                        logger.error(f"Error updating row {i}: {sheet_error}")
                        continue

            status = "✅ อัปเดตช่องว่างเป็น 0 สำเร็จ" if updated else "⏳ ไม่มีข้อมูลที่ต้องอัปเดต"
            logger.info(status)
            return status

        except Exception as e:
            error_msg = f"❌ เกิดข้อผิดพลาด: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def setup_scheduler(self):
        """Setup scheduler for daily tasks"""
        try:
            # Schedule update_absent_users to run at noon every day
            schedule.every().day.at("16:00").do(self.update_absent_users)
            
            # Start the scheduler in a separate thread
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
            
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup scheduler: {e}")
            raise
    
    def close_connection(self):
        self.conn.close()

face_system = FaceRecognitionSystem()

def sync_to_google_sheets():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # ดึงข้อมูลจาก MySQL ที่ยังไม่ได้ซิงค์ โดยเรียงตาม timestamp
            cursor.execute("SELECT * FROM check_in_out WHERE synced = 0 ORDER BY timestamp")
            rows = cursor.fetchall()

            if rows:
                # โหลดข้อมูลทั้งหมดใน Google Sheets
                data = sheet.get_all_values()
                headers = data[0]
                user_data = data[1:]  # ข้อมูลผู้ใช้

                for row in rows:
                    user_id = str(row["user_id"])
                    timestamp = row["timestamp"]
                    status = row["status"]

                    # แปลงวันที่และเวลาให้อยู่ในรูปแบบที่ต้องการ
                    date_str = timestamp.strftime("%d/%m/%y")  # เช่น "18/02/25"
                    time_str = timestamp.strftime("%H:%M")       # เช่น "12:08"

                    # สร้างชื่อคอลัมน์สำหรับ check-in/check-out ในวันที่นี้
                    checkin_col_name = f"{date_str} Check-in"
                    checkout_col_name = f"{date_str} Check-out"

                    # ตรวจสอบว่าหัวตารางมีคอลัมน์ที่ต้องการหรือไม่
                    if checkin_col_name not in headers:
                        # เพิ่มคอลัมน์ใหม่ 2 คอลัมน์สำหรับวันที่นี้
                        sheet.add_cols(2)
                        headers = sheet.row_values(1)  # โหลด header ใหม่
                        if checkin_col_name not in headers:
                            headers.extend([checkin_col_name, checkout_col_name])
                            sheet.update("A1", [headers])  # อัปเดตเฉพาะแถว header

                    # ค้นหา index ของคอลัมน์ check-in/check-out
                    try:
                        checkin_col_index = headers.index(checkin_col_name) + 1
                        checkout_col_index = headers.index(checkout_col_name) + 1
                    except ValueError:
                        print("❌ ไม่พบคอลัมน์ที่ต้องการใน header")
                        continue

                    # ค้นหาแถวของผู้ใช้ใน Sheet โดยใช้ User ID และ Name
                    user_row_index = None
                    for idx, user_row in enumerate(user_data, start=2):
                        # ตรวจสอบว่ามีอย่างน้อย 2 คอลัมน์และตรงกับ User ID
                        if len(user_row) >= 2 and str(user_row[1]).strip() == user_id.strip():
                            user_row_index = idx
                            break

                    if user_row_index is None:
                        # ถ้าไม่พบผู้ใช้ ให้ดึงข้อมูลชื่อและเพิ่มแถวใหม่
                        cursor.execute("SELECT name FROM users WHERE user_code = %s", (user_id,))
                        user = cursor.fetchone()
                        name = user["name"] if user else "Unknown"
                        
                        # เตรียมแถวใหม่ โดยจำนวนคอลัมน์ต้องตรงกับ header
                        new_row = [""] * len(headers)
                        new_row[0] = name
                        new_row[1] = user_id
                        sheet.append_row(new_row)
                        # โหลดข้อมูลใหม่
                        data = sheet.get_all_values()
                        headers = data[0]
                        user_data = data[1:]
                        # ค้นหาแถวของผู้ใช้ที่เพิ่งเพิ่ม
                        for idx, user_row in enumerate(user_data, start=2):
                            if len(user_row) >= 2 and str(user_row[1]).strip() == user_id.strip():
                                user_row_index = idx
                                break

                    # ตอนนี้ user_row_index มีค่าแล้ว
                    # ตรวจสอบว่าเซลล์ Check-in หรือ Check-out ว่างหรือไม่ก่อนอัปเดต
                    if status == "check-in":
                        current_val = sheet.cell(user_row_index, checkin_col_index).value
                        if not current_val or current_val.strip() == "":
                            sheet.update_cell(user_row_index, checkin_col_index, time_str)
                    elif status == "check-out":
                        current_val = sheet.cell(user_row_index, checkout_col_index).value
                        if not current_val or current_val.strip() == "":
                            sheet.update_cell(user_row_index, checkout_col_index, time_str)

                    # อัปเดตสถานะ sync ใน MySQL
                    cursor.execute("UPDATE check_in_out SET synced = 1 WHERE id = %s", (row["id"],))
                    conn.commit()

                print("✅ Sync completed successfully.")

            cursor.close()
            conn.close()

        except Exception as e:
            print(f"❌ Error syncing to Google Sheets: {e}")

        time.sleep(10)  # อัปเดตทุก 10 วินาที

# เริ่มรันใน background
threading.Thread(target=sync_to_google_sheets, daemon=True).start()




# WEB API
UPLOAD_FOLDER = 'faces_upload'
# สร้างโฟลเดอร์ถ้ายังไม่มี
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/upload', methods=['POST'])
def upload_image():
    try:
        if 'file' not in request.files:
            logger.warning("No file part in request")
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("No selected file")
            return jsonify({"error": "No selected file"}), 400
        
        # Read and decode image
        file_bytes = file.read()
        nparr = np.frombuffer(file_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            logger.error("Failed to decode image")
            return jsonify({"error": "Failed to decode image"}), 400
            
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}.jpg"
        
        # Recognize face
        user = face_system.recognize_faces(image)
        logger.info(f"Recognized user: {user}")
        
        if not user:
            return jsonify({"error": "ไม่พบใบหน้าในระบบ"}), 400
            
        if user == "Unknown":
            return jsonify({"name": user, "saved_image": filename})

        # Check if attendance was marked within last hour
        if face_system.check_last_notification(user[1]):
            print("Has Checked")
            return jsonify({"name": user, "message": "Checked"}), 200

        # Update notification time
        face_system.update_notification_time(user[1])
        user_id = user[1]

         # เชื่อมต่อฐานข้อมูล
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ดึงข้อมูลล่าสุดของ user_id นี้
        cursor.execute("SELECT status FROM check_in_out WHERE user_id = %s ORDER BY timestamp DESC LIMIT 1", (user_id,))
        last_record = cursor.fetchone()

        # กำหนดสถานะใหม่
        if last_record and last_record['status'] == 'check-in':
            new_status = 'check-out'
        else:
            new_status = 'check-in'

        # บันทึกลงฐานข้อมูล
        cursor.execute("INSERT INTO check_in_out (user_id, timestamp, status) VALUES (%s, %s, %s)", 
                       (user_id, now, new_status))
        conn.commit()
        
        # ปิดการเชื่อมต่อ
        cursor.close()
        conn.close()

        return jsonify({"name": user, "saved_image": filename, "message": new_status}), 200
    
    except Exception as e:
        logger.error(f"Upload error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/status', methods=['GET', 'HEAD'])
def server_status():
    return '', 200  # ส่ง Response ว่างพร้อม Status Code 200 (OK)

# ✅ ดึงข้อมูลผู้ใช้จาก MySQL
@app.route('/get_users', methods=['GET'])
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # ใช้ dictionary=True เพื่อให้คืนค่าเป็น dict
        cursor.execute("SELECT id, name, user_code FROM users ORDER BY CAST(user_code AS UNSIGNED) ASC")
        users = cursor.fetchall()
        
        cursor.close()
        conn.close()  # ✅ ปิด connection ทันทีเมื่อใช้เสร็จ
        return jsonify(users), 200

    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sort_data', methods=['POST'])
def sort_data():
    max_retries = 5  # ลองใหม่สูงสุด 5 ครั้ง
    retry_delay = 3   # หน่วงเวลา 3 วินาทีก่อนลองใหม่

    for attempt in range(1, max_retries + 1):
        try:
            records = sheet.get_all_records()
            
            if not records:
                print("✅ ไม่มีข้อมูลใน Google Sheets")
                return jsonify({"success": True, "message": "ไม่มีข้อมูลให้เรียง"}), 200

            # ฟังก์ชันแปลงค่าเป็นตัวเลข (หากเป็นค่าว่างจะไปท้ายสุด)
            def safe_int(value):
                try:
                    return int(value)
                except ValueError:
                    return float('inf')

            # ✅ เรียงข้อมูลตาม User ID
            sorted_records = sorted(records, key=lambda x: safe_int(x["User ID"]))

            # ✅ ล้าง Sheet และอัปเดตข้อมูลที่เรียงแล้ว
            sheet.clear()
            sheet.insert_row(["Name", "User ID"] + list(sorted_records[0].keys())[2:], 1)
            for row in sorted_records:
                sheet.append_row(list(row.values()))

            print("✅ เรียงข้อมูลสำเร็จ (ครั้งที่ {})".format(attempt))
            return jsonify({"success": True, "message": "เรียงข้อมูลสำเร็จ"}), 200

        except (ConnectionResetError, TimeoutError) as e:
            print(f"⚠️ Google Sheets Error (ครั้งที่ {attempt}): {e}")
            if attempt < max_retries:
                print(f"🔄 กำลังลองใหม่ใน {retry_delay} วินาที...")
                time.sleep(retry_delay)  # รอแล้วลองใหม่
            else:
                print("❌ ลองใหม่ครบทุกครั้งแล้ว แต่ยังไม่สำเร็จ")
                return jsonify({"success": False, "message": "Google Sheets Error: ลองใหม่ครบทุกครั้งแล้ว"}), 500

        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {str(e)}")
            return jsonify({"success": False, "message": f"Google Sheets Error: {str(e)}"}), 500
    
@app.route('/add_user', methods=['POST'])
def add_user():
    try:
        name = request.form.get('name')
        user_code = request.form.get('user_code')
        file = request.files.get('file')

        print(f"Name: {name}, User Code: {user_code}, File: {file.filename if file else 'No file'}")

        if not all([name, user_code, file]):
            return jsonify({"success": False, "message": "กรุณากรอกข้อมูลให้ครบถ้วน"}), 400

        # อ่านไฟล์รูปภาพเป็น numpy array
        file_contents = file.read()
        nparr = np.frombuffer(file_contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return jsonify({"success": False, "message": "ไม่สามารถอ่านไฟล์รูปภาพได้"}), 400

        # แปลงสีจาก BGR เป็น RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # ตรวจจับใบหน้า
        face_locations = face_recognition.face_locations(rgb_image)
        if not face_locations:
            return jsonify({"success": False, "message": "ไม่พบใบหน้าในรูปภาพ"}), 400

        # สร้าง face encoding
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        if not face_encodings:
            return jsonify({"success": False, "message": "ไม่สามารถประมวลผลใบหน้าได้ กรุณาตรวจสอบว่ารูปภาพชัดเจนและมีแสงสว่างเพียงพอ"}), 400

        face_encoding_bytes = face_encodings[0].tobytes()

        # ✅ บันทึกลงฐานข้อมูล MySQL
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # ตรวจสอบว่า user_code ว่างหรือไม่
            if not user_code.strip():
                return jsonify({"success": False, "message": "รหัสผู้ใช้ไม่สามารถเว้นว่างได้"}), 400
            
            # ตรวจสอบว่ามี user_code ซ้ำไหม
            cursor.execute('SELECT user_code FROM users WHERE user_code = %s', (user_code,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "รหัสผู้ใช้นี้มีอยู่ในระบบแล้ว"}), 400

            # ✅ ใช้ %s และ BLOB สำหรับ MySQL
            cursor.execute(
                'INSERT INTO users (name, user_code, face_encoding) VALUES (%s, %s, %s)',
                (name, user_code, face_encoding_bytes)
            )
            conn.commit()

            # ✅ ปิด connection หลังใช้เสร็จ
            cursor.close()
            conn.close()


            return jsonify({"success": True, "message": "เพิ่มผู้ใช้สำเร็จ"}), 200

        
        except mysql.connector.Error as e:
            return jsonify({"success": False, "message": f"เกิดข้อผิดพลาดกับฐานข้อมูล: {str(e)}"}), 500
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}), 500


@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ดึง user_code ก่อนลบ
        cursor.execute('SELECT user_code FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "ไม่พบผู้ใช้"}), 404
        user_code = str(user[0])

        # ลบข้อมูลจาก `users`
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        
        # ลบข้อมูลจาก `notifications` ตาม `user_code`
        cursor.execute('DELETE FROM notifications WHERE user_id = %s', (user_code,))

        # ลบข้อมูลจาก `check_in_out` ตาม `user_code`
        cursor.execute('DELETE FROM check_in_out WHERE user_id = %s', (user_code,))
        conn.commit()

        cursor.close()
        conn.close()

        # Retry logic for updating Google Sheet
        retry_count = 3
        attempt = 0
        success = False

        while attempt < retry_count and not success:
            try:
                # ลบข้อมูลจาก Google Sheet
                records = sheet.get_all_records()
                for idx, record in enumerate(records, start=2):  # เริ่มจากแถวที่ 2 (ข้าม header)
                    if str(record.get("User ID")) == user_code:
                        sheet.delete_rows(idx)  # ลบแถวใน Google Sheet
                        return jsonify({"success": True, "message": "ลบผู้ใช้สำเร็จ"}), 200
            except (gspread.exceptions.APIError, TransportError, TimeoutError) as e:
                    print(f"❌ Google Sheets API Error: {e}")
                    attempt += 1
                    time.sleep(2)  # รอ 2 วินาทีก่อนลองใหม่

        if success:
            return jsonify({"success": True, "message": "ลบผู้ใช้สำเร็จ"}), 200
        else:
            return jsonify({"success": False, "message": "ลบผู้ใช้ใน Google Sheet ไม่สำเร็จ"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "ไม่พบข้อมูล JSON"}), 400

        name = data.get('name')
        user_code = data.get('user_code')

        if not name or not user_code:
            return jsonify({"success": False, "message": "กรุณากรอกข้อมูลให้ครบ"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ดึงข้อมูลเดิม
        cursor.execute('SELECT user_code FROM users WHERE id = %s', (user_id,))
        old_user = cursor.fetchone()
        if not old_user:
            return jsonify({"success": False, "message": "ไม่พบผู้ใช้งาน"}), 404
        old_user_code = str(old_user[0])

        # ตรวจสอบว่า user_code ซ้ำกับผู้ใช้อื่นหรือไม่
        cursor.execute('SELECT id FROM users WHERE user_code = %s AND id != %s', (user_code, user_id))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "รหัสผู้ใช้นี้มีอยู่แล้ว"}), 400

        # อัพเดทข้อมูลใน SQLite
        cursor.execute('UPDATE users SET name = %s, user_code = %s WHERE id = %s', (name, user_code, user_id))
        conn.commit()
        conn.close()

        # Retry logic for updating Google Sheet
        retry_count = 3
        attempt = 0
        success = False

        while attempt < retry_count and not success:
            try:
                # อัพเดทข้อมูลใน Google Sheet
                records = sheet.get_all_records()
                for idx, record in enumerate(records, start=2):
                    if str(record.get("User ID")) == old_user_code:
                        sheet.update_cell(idx, 1, name)  # อัพเดทชื่อ
                        sheet.update_cell(idx, 2, user_code)  # อัพเดท User ID
                        print(f"✅ Updated {name} {user_code} to sheet success")
                success = True
            except (gspread.exceptions.APIError, TransportError, TimeoutError) as e:
                    print(f"❌ Google Sheets API Error: {e}")
                    attempt += 1
                    time.sleep(2)  # รอ 2 วินาทีก่อนลองใหม่

        if success:
            return jsonify({"success": True, "message ": "อัพเดทข้อมูลสำเร็จ"}), 200
        else:
            return jsonify({"success": False, "message": "อัพเดทข้อมูลผู้ใช้ใน Google Sheet ไม่สำเร็จ"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)