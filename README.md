# aura

Personal assistant dashboard designed for wall projection.
Built with Django — add new capabilities as Django apps over time.

## Structure

```
aura/
├── aura/           — project settings & root URL config
├── display/        — projection wall view (read-only aggregator)
├── todos/          — tasks with priority, due dates, overdue tracking
├── reminders/      — time-based alerts with recurrence support
├── templates/      — shared base templates (add later)
├── static/         — shared static files (add later)
└── manage.py
```

## First-time Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations (creates aura.db)
python manage.py migrate

# 4. Create your admin account
python manage.py createsuperuser

# 5. Start the server
python manage.py runserver
```

Then open:
- **Dashboard (projection view):** http://localhost:8000/
- **Admin panel (data entry):** http://localhost:8000/admin/

## Projection / Kiosk Mode

To display on a projected wall, open the dashboard URL in a fullscreen browser
pointed at the projected display:

```bash
# Chrome / Chromium
chrome --kiosk --noerrdialogs --disable-translate http://localhost:8000/

# Or just press F11 in any browser after opening the URL
```

The dashboard auto-refreshes data every 60 seconds.
Todos can be marked complete directly from the wall (click the item).
One-time reminders can be dismissed from the wall (✕ button).

## Adding a New App

```bash
python manage.py startapp <appname>
```

Then:
1. Add `'<appname>'` to `INSTALLED_APPS` in `aura/settings.py`
2. Build your models, register them in `admin.py`, run `makemigrations` + `migrate`
3. Add any URLs to `aura/urls.py`
4. In `display/views.py`, import and query the new model, pass to context
5. Add a new section to `display/templates/display/dashboard.html`

## Roadmap Ideas

- `routines` — recurring daily/weekly checklists
- `notes` — quick capture (therapy notes, reading log)
- `habits` — streak tracking
- REST API (Django REST Framework) for posting todos from phone/scripts
- WebSockets (Django Channels) for instant push updates
- Raspberry Pi deployment + kiosk auto-start on boot
- Arduino physical buttons for dismiss/complete
