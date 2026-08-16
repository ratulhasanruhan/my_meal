# My Meal

A private meal tracker for a daily catering subscription. Tick off the lunches and
dinners you actually took, and it works out what you owe.

- **Dashboard** — a month calendar; tap any day to toggle lunch/dinner. Running
  month cost, meal counts, and an end-of-month projection.
- **Analytics** — 12-month cost trend, weekday pattern, lunch/dinner split,
  streaks, and paid-vs-owed.
- **Settings** — the per-meal rate (versioned by date, so past months keep the
  price they were logged at) and payments to the caterer.

Responsive, light/dark, no frontend build step.

## Stack

Django 5.2 · Supabase Postgres · WhiteNoise · Vercel. Hand-written CSS and vanilla
JS — no CDN dependencies.

## Local setup

```bash
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # then fill in SECRET_KEY at minimum
python manage.py migrate        # SQLite unless DATABASE_URL is set
python manage.py createsuperuser
python manage.py runserver
```

Sign in at `/`. Set your meal rate under **Settings** before logging meals —
entries snapshot the rate in force on their date.

## Supabase

1. Supabase → **Project Settings → Database → Connection string → Transaction
   pooler** (port `6543`, not 5432 — serverless needs the pooler).
2. Put it in `.env` as `DATABASE_URL`, with your DB password substituted in.
3. `python manage.py migrate` — run migrations locally against Supabase; Vercel
   builds don't run them.

## Deploying to Vercel

Import the GitHub repo, then set these environment variables:

| Variable | Value |
|---|---|
| `SECRET_KEY` | a fresh random string |
| `DATABASE_URL` | the Supabase pooler URL |
| `DEBUG` | `False` |
| `SITE_URL` | `https://<your-app>.vercel.app` |
| `TIME_ZONE` | `Asia/Dhaka` |
| `CURRENCY_SYMBOL` | `৳` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_EMAIL` | for `bootstrap_admin` |

`vercel.json` runs two builds: the WSGI app (`config/wsgi.py`) and
`build_files.sh`, which collects static files into `staticfiles_build/static`.

Create your login user by running this locally with production `DATABASE_URL` set:

```bash
python manage.py bootstrap_admin
```

## Notes

- Meals are stored only when taken — a missing row means skipped.
- Future dates can't be logged; the API rejects them.
- Changing the rate never rewrites history. It applies from its effective date on.
