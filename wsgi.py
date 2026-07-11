"""Vercel's Python runtime auto-detects Flask and looks for a WSGI `app`
at one of a few supported entrypoint filenames — this is one of them
(spec §5, Stage 8). Locally, run.py imports `app` from here too, so
there's exactly one place the app actually gets constructed.
"""

from app import create_app

app = create_app()
