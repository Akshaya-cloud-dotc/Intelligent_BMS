# backend/alerts/__init__.py
"""
AI-PBMS alerts package.
Integrates persistent alert storage (alerts.py) with email dispatching (mailer.py).
"""

import os
import sys
import importlib.util

# Load and re-export all functions from backend/alerts.py
_curr_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_curr_dir)
_alerts_py = os.path.join(_parent_dir, "alerts.py")

if os.path.exists(_alerts_py):
    _spec = importlib.util.spec_from_file_location("_alerts_store", _alerts_py)
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _k in dir(_mod):
            if not _k.startswith("__"):
                globals()[_k] = getattr(_mod, _k)

# Expose mailer module
try:
    from . import mailer
except ImportError:
    pass
