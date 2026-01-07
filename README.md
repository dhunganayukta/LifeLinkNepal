# 🩸 Blood Donation Alert System

![Status](https://img.shields.io/badge/Status-Development-orange)
![Python](https://img.shields.io/badge/Python-3.10-blue)
![Django](https://img.shields.io/badge/Django-4.2-green)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-green)

### *"Where every drop finds a life"*

---

## 🌟 About the Project

Every year, countless lives are at risk due to delayed access to blood during emergencies. Families often post urgent requests on social media, but messages may not reach the right people in time.

**LifeLinkNepal** bridges that gap with a smart, easy-to-use system that connects blood donors with those in need, ensuring timely access to life-saving blood donations.

---

## ✨ Key Features

- 🩸 **Donor Registration**: Records donor blood types and contact information
- 🔔 **Real-time Alerts**: Notifies matching donors when blood is needed
- 🗺️ **Location-based Matching**: Finds donors near the request location
- 📱 **Easy Communication**: Direct contact between donors and recipients
- 🔐 **Secure & Private**: Protects donor information and privacy
- 📊 **Donation History**: Tracks donation records and donor availability
- 🚀 **Fast Response**: Immediate notifications to save critical time

---

## 🛠️ Technologies Used

- **Backend**: Django (Python 3.10)
- **Database**: MongoDB
- **Frontend**: HTML, CSS, JavaScript
- **Authentication**: Django Authentication System
- **Notifications**: SMS/Email integration (planned)

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.10 or higher
- MongoDB
- pip (Python package manager)
- Git

---

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/dhunganayukta/LifeLinkNepal.git
cd LifeLinkNepal
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv env

# Activate virtual environment
# On Windows:
env\Scripts\activate
# On macOS/Linux:
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=lifelink_db
```

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 7. Run the Development Server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

---

## 📱 Usage

### For Donors:
1. Register with your blood type and contact information
2. Receive alerts when your blood type is needed nearby
3. Respond to requests and save lives

### For Recipients:
1. Post an urgent blood requirement
2. System automatically notifies matching donors
3. Connect with available donors directly

---

## 📂 Project Structure

```
Lifelink/
│
├── Lifelink/                # Django project folder
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/                # App for user authentication & profiles
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── templates/accounts/
│
├── donors/                  # App for donor management
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── templates/donors/
│
├── hospital/                # App for hospital management
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── templates/hospital/
│
├── request/                 # App for handling blood requests
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── templates/request/
│
├── templates/               # Base templates
│   └── base.html
│
└── manage.py
```

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Contact & Support

**Developer**: Dhungana Yukta  
**GitHub**: [@dhunganayukta](https://github.com/dhunganayukta)

For support or queries, please open an issue in the repository.

---

## 🙏 Acknowledgments

- Thanks to all the donors who make this project meaningful
- Inspired by the urgent need for efficient blood donation systems in Nepal
- Built with ❤️ to save lives

---

## 🔮 Future Enhancements

- [ ] Mobile Application
- [ ] SMS notification system
- [ ] Blood bank integration
- [ ] Multi-language support
- [ ] Analytics dashboard
- [ ] Emergency alert system
- [ ] Donor reward/recognition system

---

**⭐ If you find this project helpful, please consider giving it a star!**
