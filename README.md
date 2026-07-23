# Camp Points, Messages & Schedule — Stage 8 (feature-complete)

**Stages 1–8 — all done:** skeleton/auth, Admin management (Users, Groups,
Rooms), Points & Penalties + Room & Roommates, Messages, the weekly
Schedule, the Staff change-request workflow, an installable PWA with real
push for new messages, and now — the last piece — timed event reminders
plus everything needed to actually deploy this to Vercel.

> Note: this file previously went stale at the Stage 3 description while
> the code moved on — it's now been rewritten to match what's actually
> here through Stage 7.

## What's new in Stage 8

- **Event reminders** (spec §4, §2.2.6) — a push 20 minutes before each
  event and again at start time. `app/reminders.py` checks for events due
  either reminder and sends via the same `send_push_to_users` helper
  Stage 7 built for messages, using `events.sent_20min_at` /
  `sent_start_at` (already in the schema since Stage 1) so a check that
  runs more than once never double-sends.
- **Not exact-minute triggered — window-based, on purpose.** Vercel Cron
  timing isn't exact (see "Cron interval limits" below), so instead of
  looking for events starting in *exactly* 20 minutes, a check asks "has
  this event's 20-minute mark passed without a reminder yet, and hasn't
  it started?" — true either way as long as *some* check runs during that
  20-minute window. Same idea for "at start," with a 3-hour cutoff so a
  long cron outage doesn't dump a pile of stale "starting now" pushes
  once checks resume.
- **`/api/cron/check-reminders`** — the endpoint Vercel Cron hits (see
  `vercel.json`). Guarded by `CRON_SECRET` when one's set (Vercel sends it
  back as an `Authorization: Bearer <secret>` header on every invocation —
  see `config.py`); unauthenticated if left blank, which is fine for
  local dev but shouldn't ship that way.
- **A manual "Run reminder check now" button** on `/admin/events` — since
  nothing triggers the cron endpoint automatically outside of an actual
  Vercel deployment, this runs the exact same check on demand so you can
  test Stage 8 locally.
- **Postgres migration** (spec §2.3) — `config.py` now rewrites whatever
  `DATABASE_URL` scheme a provider hands you (`postgres://` or
  `postgresql://`) to `postgresql+psycopg://` so SQLAlchemy uses the
  psycopg v3 driver. SQLite stays the local-dev default; nothing changes
  there.
- **`wsgi.py`** — a new root-level file exposing `app`, one of Vercel's
  supported Python entrypoint names. `run.py` now imports from it instead
  of constructing its own `Flask` instance, so there's exactly one app
  construction path shared by local dev and deployment.
- **`public/`** — static assets (CSS, JS, service worker, manifest,
  icons) are now also mirrored here. Vercel's own Flask guide recommends
  `public/**` over Flask's `static_folder` for serving assets, since files
  there are served straight from Vercel's CDN instead of invoking the
  Python function on every request. `app/static/` stays the source of
  truth for local dev (`url_for('static', ...)` is unchanged) —
  `vercel.json`'s `buildCommand` runs `sync_static.py` automatically on
  every deploy, so `public/` can't silently go stale; run it by hand
  (`python sync_static.py`) too if you want to preview a static change
  locally against the `public/` copy before pushing.
- **`vercel.json`** — runs `sync_static.py` as the build step (see above),
  and sets a `maxDuration` for the Flask function. No Cron entry — see
  "Cron interval limits" below for why reminders are piggybacked on
  ordinary traffic instead.
- **`.vercelignore`** — keeps dev-only files (`.env`, `instance/`, the
  venv, `README.md`, the two dev scripts) out of the deployed bundle.

### Cron interval limits — confirmed, not assumed (spec §5)

Checked directly against Vercel's current docs rather than assumed:

- **Hobby plan:** cron jobs can only run **once per day** — any more
  frequent schedule fails at deploy time — and even that one daily run
  isn't precise to the minute (it can fire any time within the scheduled
  hour). This is **not enough** for a "20 minutes before" reminder to be
  meaningful; on Hobby, event reminders will be unreliable/late by design
  of the plan, not a bug in this app.
- **Pro plan:** per-minute cadence is allowed. `vercel.json` here uses
  `*/10 * * * *` (every 10 minutes) — comfortably inside the 20-minute
  reminder window even accounting for imprecise firing, without paying
  for per-minute checks a camp schedule doesn't need.
- If you're on Hobby and want tighter cadence without upgrading, the
  underlying endpoint is just a plain authenticated HTTP route —
  point an external scheduler (e.g. a GitHub Actions cron, or a service
  like cron-job.org) at `/api/cron/check-reminders` with the
  `Authorization: Bearer <CRON_SECRET>` header instead of using Vercel's
  built-in Cron. Functionally identical; Vercel just isn't the one
  calling it.

## What's here (cumulative — the full spec)

- Flask app factory (`app/__init__.py`) with 5 blueprints: `auth`, `admin`,
  `staff`, `user`, `main` (which also serves `/sw.js`, the push
  subscribe/unsubscribe endpoints, and the cron reminder-check endpoint).
- Full SQLAlchemy schema (`app/models.py`) — every table from the spec,
  including every addition flagged in §2.2.
- `Role` enum (`1=ADMIN, 2=STAFF, 3=USER`) enforced via `role_required`.
- Flask-Login session auth, Flask-WTF CSRF everywhere (forms and the
  push/fetch JSON endpoints alike).
- **Admin**: full CRUD for Users, Groups, Buildings/Rooms, Points &
  Penalties, Messages, Events, and the Staff Requests review queue.
- **Staff**: everything a User sees, plus a Requests tab.
- **User/Staff dashboards**: Points & Penalties, Room & Roommates,
  Messages, and a weekly Schedule grid (past/current/upcoming).
- **PWA**: installable, with a service worker, real Web Push for new
  messages, and now timed event reminders too.
- **Deployable**: Postgres-ready config, a Vercel entrypoint, a Cron job,
  and static assets placed where Vercel's routing actually serves them.

## Setup

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python generate_vapid_keys.py   # paste the two keys it prints into .env

python seed.py   # creates all tables + seeds the Admin account
```

## Run it locally

```bash
python run.py
```

Visit `http://127.0.0.1:5000` — you'll land on `/login`. SQLite is used
automatically since `DATABASE_URL` is unset; no local Postgres needed.

## Deploying to Vercel

1. **Provision Postgres.** Create a database on Neon, Supabase, or Vercel
   Postgres, and copy its connection string.
2. **Set environment variables** in the Vercel project settings:
   `SECRET_KEY`, `DATABASE_URL` (the Postgres URL from step 1),
   `SEED_ADMIN_USERNAME`, `SEED_ADMIN_PASSWORD`, `VAPID_PUBLIC_KEY`,
   `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL`, `CRON_SECRET` (any long
   random string), and `SESSION_COOKIE_SECURE=1`.
3. **Seed the production database once**, from your machine, pointed at
   the real `DATABASE_URL`:
   ```bash
   DATABASE_URL="<your prod postgres url>" python seed.py
   ```
4. **Deploy** — push to the connected Git repo, or run `vercel deploy`
   from this directory. Vercel auto-detects Flask from `requirements.txt`
   and uses `wsgi.py` as the entrypoint; `vercel.json`'s `buildCommand`
   syncs `public/static/` and sets the function's `maxDuration`.
5. **No Cron job to confirm** — see "Cron interval limits" below.
   Reminders are checked opportunistically on ordinary request traffic
   instead (`app/reminders.py`'s `maybe_check_reminders`, wired up as a
   `before_request` hook in `app/__init__.py`), which sidesteps Hobby-plan
   Cron limits entirely. `/api/cron/check-reminders` still exists if you'd
   rather trigger checks from an external scheduler (e.g. a GitHub Actions
   cron, or Vercel Cron on a paid plan) — protect it with `CRON_SECRET` if
   you use it, since without one it's callable by anyone who finds the URL.
6. `vercel.json`'s `buildCommand` re-runs `python sync_static.py` on every
   deploy automatically, so `public/` (what actually ships) can't drift
   out of sync with `app/static/` — no manual step needed anymore.

## Functional check for this stage

1. In `/admin/events`, create an event with a start time **~15–20 minutes
   from now** (close enough to be inside the reminder window right away).
2. Make sure at least one non-Admin account (User or Staff) has clicked
   **Enable notifications** (Stage 7) in their browser.
3. Click **Run reminder check now** on `/admin/events`.
4. You should get a "Starting in 20 minutes: …" push immediately (since
   the event's already inside that window), and the event's Reminders
   column should show a "20-min sent" badge.
5. Wait until the event's start time passes (or edit it to a time in the
   past), click **Run reminder check now** again, and confirm a "Starting
   now: …" push arrives and a "Start sent" badge appears.
6. Click the button a third time with nothing new due — it should flash
   "nothing due right now" rather than re-sending anything.
7. (Optional, needs an actual Vercel deployment) Confirm the same thing
   happens automatically, driven by the Cron job instead of the manual
   button, once deployed.

This is the last planned stage — the spec (§8) is now fully built.

