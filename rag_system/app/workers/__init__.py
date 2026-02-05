"""
Workers module initialization.

This module contains Celery workers and background tasks.
Add your task modules here and they will be auto-discovered.
"""
from app.workers.celery_app import celery_app, debug_task
from app.workers.tasks import process_document, healthcheck

__all__ = [
    "celery_app",
    "debug_task",
    "process_document",
    "healthcheck",
]
