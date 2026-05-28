# 🚀 StartupIQ — AI-Powered Startup Funding Intelligence Platform

StartupIQ is a full-stack AI-powered startup funding intelligence platform designed to analyze startup investment trends, predict funding opportunities, and build a scalable SaaS ecosystem for founders, investors, and analysts.

The platform combines:

* 📊 Startup funding analytics
* 🤖 Machine learning predictions
* 🔐 Secure authentication systems
* 🌍 Global & Indian startup ecosystem insights
* 💡 Recommendation systems
* ☁️ Cloud deployment architecture

---

# 🌐 Live Demo

🔗 Deployed Application:
https://startupiq-v28l.onrender.com/

---

# 📌 Features

## 🔐 Authentication & Security

* Session-based authentication
* Google OAuth 2.0 login (Authlib)
* Secure password hashing
* Forgot password workflow
* OTP verification architecture
* PostgreSQL-backed authentication system
* Environment variable security

---

## 📊 Startup Analytics Dashboard

* Global startup funding analysis
* Sector-wise funding insights
* Country-wise investment trends
* Indian startup ecosystem analytics
* Top-funded startup rankings
* Interactive KPI dashboard
* Dynamic chart visualizations

---

## 🤖 Machine Learning Prediction Engine

Predict startup funding potential using:

* Country
* Industry
* Funding stage

### ML Features

* Random Forest Regression model
* Funding amount prediction
* Success probability estimation
* R² and MAE model evaluation

---

## 🎯 Recommendation System

Personalized startup recommendations based on:

* saved startups
* preferred industries
* user interests
* country preferences

---

## 🗄️ Database Architecture

* PostgreSQL production database
* SQLite fallback mode for development
* Connection pooling with psycopg2
* Modular database abstraction layer

---

# 🛠️ Tech Stack

## Backend

* Python
* Flask
* Flask Blueprints
* Gunicorn
* Authlib

## Frontend

* HTML5
* CSS3
* JavaScript
* Jinja2
* Chart.js

## Database

* PostgreSQL
* SQLite

## Machine Learning

* Scikit-learn
* Pandas
* NumPy
* Joblib

## Authentication & Security

* Google OAuth 2.0
* Session Authentication
* Password Hashing
* OTP Verification

## Deployment & DevOps

* Render
* Railway
* GitHub

---

# 📂 Project Structure

```bash
StartupIQ/
│
├── app.py
├── auth.py
├── db.py
├── model.py
├── requirements.txt
├── cleaned_data.csv
├── indian_startups.csv
├── model.pkl
├── encoders.pkl
│
├── templates/
├── static/
├── instance/
└── README.md
```

---

# ⚙️ Installation

## 1️⃣ Clone Repository

```bash
git clone https://github.com/yourusername/startupiq.git
cd startupiq
```

---

## 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Mac/Linux

```bash
source venv/bin/activate
```

---

## 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Variables

Create a `.env` file:

```env
SECRET_KEY=your_secret_key

DATABASE_URL=your_postgresql_database_url

GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

EMAIL_USER=your_email
EMAIL_PASS=your_email_password

BASE_URL=http://localhost:5000
```

---

# ▶️ Run Application

```bash
python app.py
```

Application runs on:

```bash
http://localhost:5000
```

---

# ☁️ Deployment

## Render Deployment

* PostgreSQL integration
* Gunicorn production server
* Environment variable configuration
* OAuth callback setup

## Railway Deployment (In Progress)

* OTP email system testing
* SMTP connectivity testing
* Production migration testing

---

# 🔒 Security Features

* Password hashing
* Secure session management
* OAuth authentication
* OTP verification architecture
* Token expiration handling
* Protected routes
* Environment variable isolation

---

# 🚧 Features In Progress

## 🔐 Authentication Improvements

* JWT Authentication
* Refresh Tokens
* Unified Email OTP Verification
* Email Verification before Signup
* Brute-force protection

---

## 🤖 AI SaaS Features

* Investor Matching System
* Founder Profiles
* Startup Scoring Engine
* AI Recommendation Engine
* Automated Data Refresh Agents
* SaaS Subscription System
* Investor Analytics Dashboard

---

# 💡 Future Vision

StartupIQ is evolving from an MVP analytics platform into a scalable AI-powered SaaS startup intelligence ecosystem that helps:

* founders discover opportunities
* investors identify promising startups
* analysts monitor funding trends
* startups predict growth potential

---

# 📈 Engineering Challenges Solved

* SQLite → PostgreSQL migration
* Google OAuth integration
* Production deployment debugging
* Recommendation engine architecture
* ML model integration
* Scalable Flask backend structure
* Cloud environment configuration

---

# 👨‍💻 Developed By

Uday M.S

---

# ⭐ Contributing

Contributions, ideas, and feedback are welcome.

---

# 📜 License

This project is currently under development and intended for educational and SaaS prototype purposes.
