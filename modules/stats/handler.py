# FILE: modules/stats/handler.py (NEW FILE)

from telegram.ext import Application, MessageHandler, filters
from .actions import show_stats

def register(application: Application) -> None:
    """Registers all handlers for the stats module."""
    
    stats_handler = MessageHandler(filters.Regex('^📊 آمار ربات$'), show_stats)
    
    application.add_handler(stats_handler)