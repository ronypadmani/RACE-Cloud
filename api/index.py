"""
Vercel Serverless Function — bridges the Flask backend to Vercel's Python runtime.
The @vercel/python runtime discovers the `app` WSGI variable automatically.
"""
import os
import sys

# ── Path Setup ────────────────────────────────────────────────
# Add backend/ to sys.path so `from app import create_app` works
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend')
sys.path.insert(0, _backend_dir)

# ── Vercel Environment Overrides ──────────────────────────────
# Vercel's filesystem is read-only except /tmp — put SQLite there
os.environ['DATABASE_PATH'] = '/tmp/racecloud.db'

# Default to demo mode on Vercel (no persistent storage for real data)
os.environ.setdefault('DEMO_MODE', 'true')
os.environ.setdefault('DEMO_FILE', 'high_cost.json')

# ── Create Flask App ──────────────────────────────────────────
from app import create_app

app = create_app()
