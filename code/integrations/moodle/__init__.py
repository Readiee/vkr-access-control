"""Адаптер интеграции с Moodle (режим Б — single PDP)."""
from .adapter import MoodleCourseImporter
from .moodle_client import MoodleClient
from . import translators

__all__ = ["MoodleCourseImporter", "MoodleClient", "translators"]
