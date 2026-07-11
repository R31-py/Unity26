"""Re-sync public/ from app/static/ — Stage 8.

Vercel's Flask guide recommends serving static assets from a top-level
public/** directory (CDN-served, bypasses the Python function entirely)
rather than Flask's own static_folder. To avoid maintaining two copies by
hand, app/static/ stays the single source of truth for local dev
(url_for('static', ...) keeps working exactly as before) and this script
mirrors it into public/static/ — same relative paths, so the generated
URLs match either way. The service worker also gets a copy at public/sw.js
so it's served at the root path Vercel's CDN, without needing the
Flask /sw.js route to be hit at all in production (that route stays as
the local-dev fallback and still works if the CDN copy is ever missing).

Run this after adding/editing anything under app/static/, before
deploying.

Usage:
    python sync_static.py
"""

import shutil
from pathlib import Path

BASE = Path(__file__).parent
SRC = BASE / "app" / "static"
DEST = BASE / "public" / "static"
SW_SRC = SRC / "sw.js"
SW_DEST = BASE / "public" / "sw.js"


def main():
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(SRC, DEST)
    shutil.copy2(SW_SRC, SW_DEST)
    print(f"Synced {SRC} -> {DEST}")
    print(f"Synced {SW_SRC} -> {SW_DEST}")


if __name__ == "__main__":
    main()
