# Face Recognition Attendance System

A real-time face recognition system for attendance tracking with web interface and Google Sheets integration.

![Face Recognition System](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

## 🎯 Features

- **Real-time Face Recognition**: Advanced face detection and recognition using OpenCV and face_recognition
- **Web Interface**: Modern responsive UI for camera access and user management
- **Database Integration**: MySQL database for storing user data and attendance records
- **Google Sheets Sync**: Automatic synchronization with Google Sheets for attendance tracking
- **User Management**: Add, edit, and delete users through web interface
- **Attendance Tracking**: Automatic check-in/check-out system with timestamp
- **Multi-camera Support**: Support for multiple camera devices
- **Notification System**: Real-time attendance notifications and logging

## 🖼️ Screenshots

### Main Interface
![Main Interface](https://i.ibb.co/KjvYGFQF/Screenshot-2568-06-20-at-20-05-44.png)

### User Management
![User Management](https://i.ibb.co/MyKQVmff/Screenshot-2568-06-20-at-20-06-13.png)

### Google Sheets Integration
![Google Sheets](https://i.ibb.co/RTvw65kV/Screenshot-2568-06-20-at-20-15-19.png)

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- MySQL Server
- Webcam/Camera device
- Google Account for Sheets integration

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/9teeedev/face-recognition-attendance.git
cd face-recognition-attendance
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up MySQL Database**
```bash
# The application will automatically create the database and tables
# Make sure MySQL server is running on localhost:3306
```

4. **Configure Google Sheets API** (See detailed guide below)

5. **Run the application**
```bash
cd server
python app.py
```

6. **Open the web interface**
```
http://localhost:5000
```

## 📋 Requirements

Create a `requirements.txt` file in your project root:

```
flask==2.3.3
flask-cors==4.0.0
opencv-python==4.8.1.78
numpy==1.24.3
face-recognition==1.3.0
mysql-connector-python==8.1.0
gspread==5.10.0
oauth2client==4.1.3
google-api-python-client==2.95.0
schedule==1.2.0
```

## 🔧 Configuration

### Database Configuration

Edit the database connection settings in `server/app.py`:

```python
def get_db_connection():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="your_mysql_username",
        password="your_mysql_password",
        database="facedetection"
    )
```

### Google Sheets Configuration

1. Update the `SPREADSHEET_ID` in `server/app.py`:
```python
SPREADSHEET_ID = "your_google_sheet_id"
```

1. Place your Google Service Account key file as `yourname-43df466db92f.json` in the server directory.

## 🔑 Google Service Account Setup Guide

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "Face Recognition System")
4. Click "Create"


### Step 2: Enable Required APIs

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
2. Search and enable the following APIs:
   - **Google Sheets API**
   - **Google Drive API**

### Step 3: Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Fill in the service account details:
   - **Service account name**: `face-recognition-service`
   - **Service account ID**: Will be auto-generated
   - **Description**: `Service account for face recognition attendance system`
4. Click "Create and Continue"


### Step 4: Generate and Download Key File

1. In the service account list, click on your newly created service account
2. Go to the "Keys" tab
3. Click "Add Key" → "Create new key"
4. Select "JSON" format
5. Click "Create"
6. The key file will be downloaded automatically

![Download Key](https://i.ibb.co/S43qqZM3/Screenshot-2568-06-20-at-20-17-42.png)

### Step 5: Configure Google Sheets

1. Create a new Google Sheet or use an existing one
2. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
   ```
3. Share the sheet with your service account email:
   - Click "Share" button in Google Sheets
   - Add the service account email (found in the JSON key file)
   - Give "Editor" permissions

[Google Sheet](https://docs.google.com/spreadsheets/d/16efc_Flx9j-0tpl0tj9UHexsodPod1CJcaIbNkR_Wk0/edit?usp=sharing)

### Step 6: Place Key File

1. Rename the downloaded JSON file to `yourname-43df466db92f.json`
2. Place it in the `server/` directory of your project

## 📁 Project Structure

```
face-recognition-attendance/
├── server/
│   ├── app.py                          # Main Flask application
│   ├── teeedev-43df466db92f.json      # Google Service Account key
│   └── faces_upload/                   # Uploaded face images
├── client/
│   ├── index.html                      # Main web interface
│   ├── manage_user.html               # User management interface
│   └── assets/                        # CSS, JS, images
├── docs/
│   └── images/                        # Documentation images
├── requirements.txt                    # Python dependencies
└── README.md                          # This file
```

## 🎮 Usage

### Adding New Users

1. Open the web interface
2. Click "Manage Users"
3. Fill in user details:
   - **Name**: Full name of the user
   - **User Code**: Unique identifier (numbers recommended)
   - **Photo**: Clear front-facing photo
4. Click "Add User"

### Attendance Tracking

1. Users stand in front of the camera
2. System automatically detects and recognizes faces
3. Attendance is logged with timestamp
4. Data is synchronized to Google Sheets automatically

### Managing Data

- **View Users**: All registered users are listed in the management interface
- **Edit Users**: Update name and user code
- **Delete Users**: Remove users and all associated data
- **Sort Data**: Organize Google Sheets data by User ID

## 🔄 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload image for face recognition |
| GET | `/get_users` | Retrieve all registered users |
| POST | `/add_user` | Add new user with face data |
| PUT | `/update_user/<id>` | Update user information |
| DELETE | `/delete_user/<id>` | Delete user and associated data |
| POST | `/sort_data` | Sort Google Sheets data |
| GET/HEAD | `/status` | Check server status |

## 🛠️ Troubleshooting

### Common Issues

1. **Camera not working**
   - Check camera permissions in browser
   - Try different camera devices
   - Ensure proper lighting

2. **Face not recognized**
   - Ensure good lighting conditions
   - Face should be clearly visible and front-facing
   - Check if user is registered in the system

3. **Google Sheets sync issues**
   - Verify service account permissions
   - Check internet connection
   - Ensure correct spreadsheet ID

4. **Database connection errors**
   - Verify MySQL server is running
   - Check database credentials
   - Ensure database exists (will be auto-created)

### Debug Mode

To enable debug mode, set `debug=False` in `app.py`:

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Credits

**Developed by:** [9teeedev](https://github.com/9teeedev)

Special thanks to the open-source community and the following libraries:
- [face_recognition](https://github.com/ageitgey/face_recognition)
- [OpenCV](https://opencv.org/)
- [Flask](https://flask.palletsprojects.com/)
- [gspread](https://github.com/burnash/gspread)

---

⭐ **If you find this project helpful, please give it a star!** ⭐
