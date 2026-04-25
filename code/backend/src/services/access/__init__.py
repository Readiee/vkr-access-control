"""AccessService и приватный AccessExplainer для трассировки блокировок

Наружу — только AccessService. _explanations вызывается только из service.py
"""
from services.access.service import AccessService

__all__ = ["AccessService"]
