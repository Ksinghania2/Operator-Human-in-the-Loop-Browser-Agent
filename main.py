"""Shim so both `uvicorn main:app` and `uvicorn app.main:app` work.

The real application lives in :mod:`app.main`; this module just re-exports ``app``.
"""
from app.main import app  # noqa: F401
