## Date Nite (Django + Gemini)

Simple Valentines-themed voting app for a couple to plan a night out.

### Features

- Invite a partner by email and generate unique voting links for each person.
- Collect each person's choices (dinner, activity, sweets, budget) and store them in SQLite.
- Show shared results when both votes are in.
- Generate a date-night itinerary with Gemini when `GEMINI_API_KEY` is configured.

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
DEFAULT_FROM_EMAIL=noreply@datenite.local
```

If `GEMINI_API_KEY` is not set, the app still works and shows a fallback summary instead of AI output.

### Notes

- Development email uses Django console backend (`EMAIL_BACKEND=console`), so invite emails print to terminal.
- SQLite is the default database in development.
- For production, switch `DATABASES` in `config/settings.py` to PostgreSQL.
