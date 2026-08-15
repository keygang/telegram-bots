"""
Admin Telegram Bot Package
Provides remote configuration management for all Telegram bot instances and NoSQL prompt presets.
"""

from .bot import run_admin_bot

__all__ = ["run_admin_bot"]
