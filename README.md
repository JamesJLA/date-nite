## Date Nite (Django + Gemini)

Date Nite is a couples planning app where two people submit preferences and get one shared date-night plan.

### Live app

https://date-nite-tuwrj.ondigitalocean.app/

### How it works

1. One partner creates an invite and sends a private voting link.
2. Each person submits their ideal date and personalized vote answers.
3. The app combines both responses into shared results.
4. Gemini can generate or refine a final date-night story (with a local fallback if AI is unavailable).

### Features

- Invite a partner by email and generate unique voting links for each person.
- Create an account to keep your saved date plans and partner connections.
- Collect each person's detailed choices (dinner, activity, sweets, budget, mood, duration, transport, notes) and store them in SQLite.
- Show shared results when both votes are in.
- Generate a cleaner date-night story using Gemini only when you click the button.
- Optionally add a city so the plan is localized.
- Uses browser locale (`Accept-Language`) plus optional city to localize tone and suggestions.
- Includes a second-round refinement form so couples can request changes to the first result.

### Local setup

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

### Environment setup

Create a `.env` file in the project root:

```env
SECRET_KEY=replace-with-a-secret-value
DEBUG=True
GEMINI_API_KEY=your-key-here
ENABLE_AI=True
DEFAULT_FROM_EMAIL=noreply@datenite.local
```

Provider is Gemini.
If no Gemini key works, the app still generates a local fallback date plan.

### Notes

- Development email uses Django console backend (`EMAIL_BACKEND=console`), so invite emails print to terminal.
- SQLite is the default database in development.
- Production uses `DATABASE_URL` (recommended: DigitalOcean Managed PostgreSQL).

### Deploy to DigitalOcean App Platform

First thing to do in DigitalOcean:

1. Create a new **App** from this GitHub repository.
2. Add a **Managed PostgreSQL** database component to the app.
3. Add required app env vars:
   - `DEBUG=False`
   - `SECRET_KEY=<strong-random-value>`
   - `ALLOWED_HOSTS=<your-app-domain>`
   - `CSRF_TRUSTED_ORIGINS=https://<your-app-domain>`
   - `DATABASE_URL` (from the managed database)
   - `GEMINI_API_KEY=<optional but recommended>`

Suggested service commands:

- Build command: `python manage.py collectstatic --noinput`
- Run command: `python -m gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
- Release command: `python manage.py migrate`

Health check path: `/healthz`
