# 💘 Matchmaking Dating App – Backend API

A scalable **Django backend** for a modern matchmaking platform with realtime chat, geolocation-based discovery, subscriptions, and audio/video calling.

🔗 GitHub: https://github.com/TechbyAbrar/match-making-app.git
🎨 Figma: https://www.figma.com/design/Rx9HiVKLQ9ipxW1LTj6NYw/krystalmp7-%7C%7C--matchmaking-app

---

## 🚀 Overview

This backend powers a **dating / matchmaking application** with core features found in modern platforms:

* user matching system
* realtime messaging
* location-based discovery
* subscription-based access
* audio/video calling

Built with a **production-ready architecture** using Django, Redis, Celery, and ASGI.

---

## 🧠 Key Features

* JWT Authentication (custom login: email / phone / username)
* ❤️ Mutual matching system
* 📍 Geo-based user discovery (PostGIS + GeoDjango)
* 💬 Realtime chat (ASGI + Redis)
* 🔔 Notifications system
* 📞 Audio & video calls (Agora)
* 💳 Subscription system
* ⚡ Background jobs (Celery + Beat)
* 🧾 Structured logging

---

## 🏗️ Architecture

```text
Client → API (Django ASGI)
            ↓
   Auth + Match Engine
   Chat + Notification
   Subscription + Calls
            ↓
   PostgreSQL (PostGIS)
            ↓
   Redis (cache + queue + realtime)
            ↓
   Celery (async jobs)
```

---

## ⚙️ Tech Stack

* Django 5 + DRF
* PostgreSQL + PostGIS
* Redis (cache + pub/sub)
* Celery + Celery Beat
* ASGI (Gunicorn + Uvicorn)
* GeoDjango
* Agora (calls)
* OneSignal (notifications)

---

## ⚡ Run Locally

### 1. Setup

```bash
git clone https://github.com/TechbyAbrar/match-making-app.git
cd match-making-app

python -m venv env
source env/bin/activate

pip install -r requirements.txt
```

---

### 2. Run services

#### Redis

```bash
redis-server
```

#### Celery Worker

```bash
celery -A core worker -l info
```

#### Celery Beat

```bash
celery -A core beat -l info
```

---

### 3. Run Backend (ASGI)

```bash
gunicorn core.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

---

## 📡 API

Swagger:

```text
/api/schema/swagger-ui/
```

---

## 🌐 Environment (.env)

```env
SECRET_KEY=your-secret
DATABASE_URL=postgis://user:password@host:port/db

AGORA_APP_ID=your-id
AGORA_APP_CERTIFICATE=your-secret
```

---

## 🧠 Why This Project Matters

This is not a basic CRUD backend.

It demonstrates:

* realtime system design
* distributed components (Redis + Celery)
* geospatial queries
* async processing
* production deployment patterns

---

## 👨‍💻 Author

Abrar (TechbyAbrar)
Backend Engineer – Django | Realtime Systems | AI-ready APIs
