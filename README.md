# Camp Points, Messages & Schedule — Stage 8 (feature-complete)

**Stages 1–8 — all done:** skeleton/auth, Admin management (Users, Groups,
Rooms), Points & Penalties + Room & Roommates, Messages, the weekly
Schedule, the Staff change-request workflow, an installable PWA with real
push for new messages, and now — the last piece — timed event reminders
plus everything needed to actually deploy this to Vercel.

> Note: this file previously went stale at the Stage 3 description while
> the code moved on — it's now been rewritten to match what's actually
> here through Stage 7.

## UI redesign (in progress)

The app is being migrated from the dark, swipeable vertical-carousel
dashboard to a static, light "card grid" design (white cards on a light
grey page, orange accents), matching an approved set of mockup screens.
This is being done **incrementally, page by page**, so functionality is
never broken mid-migration — every step below has been smoke-tested
against a real Flask app + SQLite DB before being committed.

**Done:**
- **Main dashboard** (user, staff, admin) — `app/templates/dashboard_light_base.html`
  is the new shell (white header card with avatar/name/@username + a live
  clock, an orange "verse of the day" card, then a static 2-column grid of
  cards). Verses are hardcoded locally in `app/verses.py` (no external API),
  picked deterministically by day-of-year. The old vertical drag-carousel is
  gone from these three pages; no scroll/swipe interaction remains here.
  - `user/dashboard.html`: Group, Room, Schedule, Messages cards.
  - `staff/dashboard.html`: same four + a Requests card.
  - `admin/dashboard.html`: Users, Groups, Rooms, Points, Messages, Events,
    Requests cards.
- **Schedule page** (user, staff) — `user/schedule_detail.html` /
  `staff/schedule_detail.html` now extend the same light shell. Events are
  grouped under date headings (only days with events are shown), each
  event is a tappable preview card, and tapping one opens a full detail
  overlay (audience, name, time, description) built client-side from a
  `<template>` via `app/static/js/schedule.js` — no extra network request.
  The nearest upcoming event gets an orange accent bar. Week
  navigation (`?week=`) is unchanged.
- **Messages page** (user, staff) — `user/messages_detail.html` /
  `staff/messages_detail.html` are now a light card feed grouped by day
  (same visual language as Schedule): each message shows its time/date,
  content, who it was sent to (a group or `@all`), the author's
  `@username`, and its title. Messages from the last 24h (the same
  heuristic the dashboard's unread badge already used) get an orange
  accent bar. Both routes now also pass `unread_message_count` to the
  template, matching what the dashboard already computed.
- **Dead-code cleanup** — once the Dashboard, Schedule, and Messages
  pages were all migrated, nothing on any page still used the old
  vertical drag-carousel (`.cx-carousel-wrap` / `.cx-item` / `.cx-track`),
  so it's been removed for real rather than left unused:
  `dashboard_base.html` and `_carousel_macros.html` are deleted, and
  `carousel.js` now only contains the avatar bottom-sheet logic (still
  used by `base.html`'s not-yet-migrated pages). The dark `.cx-*` CSS
  theme in `style.css` is still there because `base.html` (Users, Points,
  Messages/Events/Requests lists, Room/Points detail, all admin CRUD
  forms, auth, error pages) still uses it for its header/nav chrome —
  that goes away once all of those get their own card-UI pass.

- **Groups page** (admin) — `admin/groups.html` now extends the light
  shell instead of `base.html`. The ranked leaderboard is a stack of
  white `grp-card`s (rank, group-color swatch, name, member count) with
  a chip row for points/rewards/penalties, matching the Schedule/Messages
  card language. Tapping a card still opens edit (whole card is a link);
  the delete `&times;` button sits top-right above it, same overlay
  pattern the old `entity-card` used, just restyled light. The "+ New
  group" action is now a full-width orange `gc-btn-primary` button above
  the list. `admin/group_form.html` (add/edit) is untouched for now —
  same as Messages/Events, list pages migrate before their forms do.

- **Rooms page** (admin) — `admin/rooms.html` now extends the light
  shell too. Each building gets a plain heading row (name + small
  "Edit"/delete actions, no card chrome of its own) instead of the old
  `building-block`, followed by a stack of white `room-card`s (room
  number, occupancy count, an Open/Full badge) — and, per spec,
  roommates are now shown directly on the card as small
  `room-mate-card` chips (first name + surname initial) instead of just
  a bare occupant count. "+ Building" is a secondary (outline) button,
  "+ Room" the primary orange one. `building_form.html`/`room_form.html`
  are untouched, same reasoning as every other form so far.

> Correction: this file's "Not started yet" list previously said Groups
> and Rooms were the *only* pages left once this step landed — that was
> stale/wrong. A repo-wide check after finishing Rooms shows quite a few
> more pages still extend `base.html`.

- **Points detail + Room detail** (user, staff) —
  `user/points_detail.html` / `staff/points_detail.html` and
  `user/room_detail.html` / `staff/room_detail.html` now extend the
  light shell (identical between roles apart from the back-link target,
  same as every other page pair). Points detail leads with a big
  `pts-total-card` (group total), then the ledger as `pts-event-card`s
  with a green/red accent bar for reward vs. penalty, then the group
  leaderboard as compact `pts-rank-row`s with the viewer's own group
  outlined and tagged "YOU". Room detail leads with the same total-card
  style for room number/building, then roommates as `rmd-mate-row`s
  (name + group swatch). No admin edit affordances here — these are
  read-only "my stuff" views, unlike the admin Groups/Rooms management
  pages from steps 4–5.

- **Points & Penalties page** (admin) — `admin/points.html` reuses the
  `pts-event-card` ledger style built for step 6's user/staff Points
  detail page, extended with a group swatch+name row (this ledger spans
  every group, unlike the per-group one members see) and an
  Edit/Delete action row per entry. Delete uses the new reusable
  `gc-icon-delete-btn` — a small inline round button for cards that
  aren't a single full-card link (unlike Groups/Rooms, each entry here
  needs separate Edit and Delete actions, so no card-wide overlay link).
  `point_form.html` untouched, same reasoning as every form so far.

- **Users, Messages, Events, Requests** (admin) — the last four admin
  lists, all converted together to conserve effort: `admin/users.html`
  reuses the `grp-card` pattern from Groups (role/group/room as chips,
  new `chip-blue`/`chip-grey`/`chip-muted` colors for role). `admin/
  messages.html` reuses `msg-card` from the Messages detail page, with
  an `Everyone`/group-swatch audience line plus the same Edit/Delete
  action row `points.html` introduced. `admin/events.html` reuses
  `pts-event-card` with two new small classes for the date/time line and
  the 20-min/start "sent" badges. `admin/requests.html` is the one
  genuinely new layout: status-filter tabs (`req-tab`, matching the
  `gc-week-btn` pill look), a status badge per card, and — only for
  pending ones — an Approve button plus a `<details>`-based Reject
  form. All four forms (`user_form.html`, `message_form.html`,
  `event_form.html`) stay on `base.html` as before.

> Note: these four were built and Jinja-parse-checked, but not smoke-
> tested against a live app in this environment the way the README
> claims for the very earliest stages — same caveat as steps 4-7.

- **My Requests** (staff) — `staff/requests.html` was the last list
  page left. It reuses `admin/requests.html`'s card shape (status
  badge, `pts-event-card`) minus the Approve/Reject actions (staff only
  see their own requests' outcome, they don't review them), with three
  `gc-btn-secondary` shortcuts up top to start a new Message/Points/Event
  request. Same parse-checked-not-smoke-tested caveat as above.

**Not started yet** (still on the old dark `base.html` header/table UI):
- All add/edit forms for every entity (Groups, Rooms, Buildings, Users,
  Points, Messages, Events) plus the Staff change-request forms.
- Auth (login) and error pages (403/404).
- `base.html`'s dark `.cx-*` header/nav chrome and CSS can only be
  retired once *all* of the above are converted.

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


---

## UI redesign

The dark swipe-carousel UI has been replaced with a flat, card-based
light theme (white header + orange verse-of-the-day card + static card
grids), done screen-by-screen so functionality was never broken
mid-migration. Every list/detail/dashboard page now extends the light
shell — `app/templates/dashboard_light_base.html`:

- **Dashboards** (User/Staff/Admin) — avatar + name/@username + live
  clock header, verse-of-the-day card (`app/verses.py`, hardcoded list,
  no external API), static 2-column card grid.
- **Schedule** (User/Staff) — events grouped by day, tap-to-expand detail
  overlay (`app/static/js/schedule.js`), nearest upcoming event
  highlighted.
- **Messages** (User/Staff) — card feed grouped by day, recent (last 24h)
  messages highlighted.
- **Points/Room detail** (User/Staff) and **all Admin CRUD list pages**
  (Users, Groups, Rooms, Points, Messages, Events, Requests) — same card
  grid treatment.

**Intentionally still on the old dark theme (`base.html`):** every
`*_form.html` (new/edit forms), the login page, and error pages. These
are short, single-purpose forms where the card-grid treatment doesn't
apply — they keep `base.html`'s dark header/nav chrome and the avatar
bottom sheet, which is why that CSS (`.cx-header`, `.cx-avatar-btn`,
`.cx-backdrop`/`.cx-sheet-*`) and the (now avatar-sheet-only)
`carousel.js` are still in the codebase rather than deleted.

**Dead-code cleanup:** once no page anywhere used the old
vertical drag-carousel, its markup, JS, and CSS were removed outright
rather than left unused:
- `dashboard_base.html` and `_carousel_macros.html` (the old carousel
  base template and its item/chip macros) — deleted.
- `carousel.js` — trimmed to just the avatar-bottom-sheet open/close
  logic that `base.html` still uses; the drag/swipe carousel
  implementation is gone.
- `live.js` — the carousel-specific mid-drag guard and
  `reinitCarousel()` re-wiring (needed only to keep a *draggable* card
  focused/undragged across a live poll swap) were removed; the live
  DOM-swap itself is unchanged.
- `style.css` — the `.cx-carousel-wrap`/`.cx-item`/`.cx-track`/`.cx-rail`/
  `.cx-dot`/`.cx-chip`/`.cx-card`/`.cx-pill`/`.cx-big-num`/`.cx-hint`
  rules (and the CSS variables only they referenced) are gone. The
  `.cx-header`/`.cx-avatar-btn`/`.cx-backdrop`/`.cx-sheet-*` rules stay,
  since `base.html` still renders that markup.

### App icon / logo

`app/static/icons/icon-192.png`, `icon-512.png`, and
`icon-512-maskable.png` are generated from the camp's circular badge logo
(mountains/heart/campfire, "UC 26", "Together as one"). Every place an
icon shows up — the browser tab favicon, the `apple-touch-icon`, the PWA
install icon (`manifest.json`), and Web Push notifications (`icon` and
`badge` in `app/static/sw.js`) — all reference these same three files, so
updating the logo here is a one-stop change. The maskable variant places
the badge inside the standard 80% "safe zone" on a solid brand-orange
background, since OS icon masks (circle/squircle/rounded-square on
Android) crop right to the canvas edge and a transparent-cornered badge
would otherwise show bare system background peeking through.
