# My Meal

A private meal tracker for a daily catering subscription. It runs off a standing
plan, so it counts your meals on its own — you only step in when a day differs.

- **Dashboard** — month calendar, quantity steppers for today, running cost and
  what you owe including anything carried over. Tap a day to adjust it;
  long-press to change it going forward.
- **Report** — the monthly statement: brought-forward balance, this month's
  meals, payments, and what's still to pay. Plus guest-meal cost, eating runs,
  gaps, and a day-by-day table.
- **Analytics** — 12-month cost trend, weekday pattern, lunch/dinner split,
  streaks and gaps.
- **Settings** — the meal plan, the per-meal rate, and payments.

Responsive, light/dark, no frontend build step.

## How the counting works

Three layers, in order of precedence:

1. **A one-day override** — you changed that specific day.
2. **The plan** — a standing rule like "Dinner ×1 every day from 1 July", or a
   weekday-scoped one like "Lunch ×0 every Friday". The newest applicable rule
   wins; on the same date, a weekday rule beats an every-day rule.
3. **Nothing before your plan starts** — turning the app on never back-bills you.

Quantities above 1 are guest meals, and the report prices them separately.

Money works as a running ledger: each month opens with the previous month's
closing balance, so an unpaid amount rolls forward as due and an overpayment
sits as advance.

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

Sign in at `/`, then under **Settings** set:

1. **The meal rate** — versioned by date, so a later rate hike never rewrites
   past months.
2. **The meal plan** — usually Lunch ×1 and Dinner ×1 from the day you joined the
   service. Nothing is counted until a plan exists.

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
