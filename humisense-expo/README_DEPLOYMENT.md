# HUMISENSE — cPanel Deployment Guide

Deploy to typical cPanel shared hosting that supports Python / Flask via
**Setup Python App** (Passenger / WSGI). No Docker, Node.js, npm, Redis,
Celery or PostgreSQL required.

---

## Steps

1. **Create a Python app in cPanel**
   - *Setup Python App* → **Create Application**.
   - Choose a Python version (3.9+ recommended).
   - Application root: point at the `humisense-expo` folder (e.g.
     `/home/user/humisense`).
   - Application URL: your domain / subdomain.
   - Startup file: `passenger_wsgi.py`.

2. **Upload the project**
   - Upload the contents of `humisense-expo/` to the application root
     (via File Manager or FTP).

3. **Install requirements**
   - In cPanel *Setup Python App* → your app → **Run Pip Install**, or in SSH:
     ```bash
     pip install -r requirements.txt
     ```

4. **Create a MySQL database (optional)**
   - *MySQL Databases* → create database + user.
   - Import `schema.sql` into the database (phpMyAdmin → Import).
   - Add the connection variables (next step). If you skip MySQL,
     SQLite is used automatically — no setup needed.

5. **Add environment variables**
   - In *Setup Python App* → your app → **Environment Variables**:
     ```
     SECRET_KEY=your-random-secret
     DB_HOST=localhost            (leave unset to use SQLite)
     DB_NAME=username_humisense
     DB_USER=username_humisense
     DB_PASSWORD=your-db-password
     DEMO_MODE=true
     AI_PROVIDER=mock
     ```
   - Never commit a real `.env` file or API keys.

6. **Restart the application**
   - *Setup Python App* → your app → **Restart**.

7. **Open your domain** and run the demo.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| **500 error** | WSGI startup failure | Check `error.log` / `passenger.log`. Ensure `passenger_wsgi.py` exists and imports `app` (`from app import app as application`). |
| **Missing module** | Requirements not installed | Run *Pip Install* in cPanel, or `pip install -r requirements.txt` from SSH. Check the Python version matches the app. |
| **Database connection** | Bad DB credentials or missing schema | Verify `DB_*` env vars, that the DB user has privileges on the database, and that `schema.sql` was imported. Set `DB_HOST` empty to fall back to SQLite while debugging. |
| **Permissions** | Files not readable by the app user | Ensure files are owned by your cPanel user and `passenger_wsgi.py` is readable. |
| **Passenger restart needed** | `.env` / code changes not applied | Restart the Python app in cPanel after every change. |

## Notes

- Production runs through Passenger/WSGI. `app.run()` at the bottom of
  `app.py` is only for local development and never executes under Passenger.
- The demo works with **no AI API key**. If you later configure a live
  provider and it fails, the app automatically falls back to Demo AI so the
  presentation never breaks.
- API keys are masked and never logged.