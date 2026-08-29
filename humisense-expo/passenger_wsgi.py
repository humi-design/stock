"""cPanel/Passenger WSGI entry point."""
import os
import sys

# Ensure this directory is on the path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DEMO_MODE", "true")

from app import app as application  # noqa: E402