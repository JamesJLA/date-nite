## Date Nite (Django + Gemini)

Simple Valentines-themed voting app for a couple to plan a night out.

### Features

- Invite a partner by email and generate unique voting links for each person.
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
- For production, switch `DATABASES` in `config/settings.py` to PostgreSQL.
