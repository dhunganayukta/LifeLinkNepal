# LifeLinkNepal 🩸

**A real-time blood donation alert system connecting donors with hospitals across Nepal.**

[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com)
[![Neon](https://img.shields.io/badge/Neon-PostgreSQL-00E699?style=flat&logo=postgresql&logoColor=white)](https://neon.tech)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> *"Where every drop finds a life"*

---

## Overview

Delayed access to blood during emergencies costs lives. LifeLinkNepal is a Django-based web platform that bridges donors and hospitals — matching blood types, sending real-time alerts, and enabling direct communication when every minute matters.

Built for Nepal's healthcare context, the system supports both donor self-registration and hospital-initiated emergency requests. Data is stored on [Neon](https://neon.tech) — a serverless PostgreSQL platform.

---

## Features

- **Donor Registration** — Blood type, contact details, and availability tracking
- **Hospital Dashboard** — Post blood requests, manage emergencies, view nearby donors
- **Smart Matching** — Notifies eligible donors based on blood type and proximity
- **Notification System** — Donors receive and respond to requests directly
- **Donation History** — Full audit trail per donor
- **Super Admin Panel** — Platform-wide management and oversight
- **REST API** — Serializer-based API layer (`api/`) for future mobile integration

---

## Project Structure

```
LifeLinkNepal/
├── accounts/               # Auth, registration, user profiles
├── api/                    # REST API (serializers, views, urls)
├── algorithms/             # Matching logic for donor-request pairing
├── donors/                 # Donor profiles, tasks, notifications
│   ├── models.py
│   ├── views.py
│   ├── tasks.py            # Background notification tasks
│   └── utils.py
├── hospitals/              # Hospital profiles, blood requests, emergency flow
│   └── management/         # Custom management commands
├── templates/
│   ├── donors/             # Donor dashboard, history, request detail
│   ├── hospitals/          # Hospital dashboard, blood request forms
│   ├── base.html
│   ├── home.html
│   └── super_admin_dashboard.html
├── static/
├── manage.py
├── requirements.txt
└── Procfile                # Deployment config
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip
- Git

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/dhunganayukta/LifeLinkNepal.git
cd LifeLinkNepal

# 2. Create and activate virtual environment
python -m venv env
source env/bin/activate        # macOS/Linux
# env\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env           # Edit with your values
```

`.env` file:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=postgresql://user:password@ep-xxxx.neon.tech/dbname?sslmode=require
```

```bash
# 5. Run migrations
python manage.py migrate

# 6. Start the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`

---

## Usage

**Donors**
1. Register with blood type and location
2. Receive alert when a matching request is posted
3. Accept or decline — hospital is notified immediately

**Hospitals**
1. Log in and post a blood request (type, urgency, quantity)
2. System notifies matching donors automatically
3. Track responses from the hospital dashboard

**Super Admin**
- Full platform visibility via `/super_admin_dashboard`
- Manage users, hospitals, and requests

---

## API

A REST API is available under `/api/` for third-party or mobile integrations.

Key endpoints (see `api/urls.py` for full list):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/donors/` | List available donors |
| POST | `/api/requests/` | Submit a blood request |
| GET | `/api/requests/<id>/` | Request details |

---

## Roadmap

- [ ] SMS notifications (Sparrow SMS / Twilio)
- [ ] Mobile app (React Native)
- [ ] Live location-based donor map
- [ ] Blood bank inventory integration
- [ ] Multi-language support (Nepali / English)
- [ ] Donor recognition and reward system
- [ ] Analytics dashboard for hospitals

---

## Contributing

Pull requests are welcome.

```bash
git checkout -b feature/your-feature
git commit -m "Add your feature"
git push origin feature/your-feature
```

Then open a Pull Request against `main`.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Yukta Dhungana**  
[@dhunganayukta](https://github.com/dhunganayukta)

---

*Built to save lives. One notification at a time.*