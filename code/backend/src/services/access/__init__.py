"""AccessService (DSL §36) + приватный AccessExplainer (UC-9 SLD-trace).

Наружу экспортируется только AccessService. _explanations — приватный helper,
вызывается только из service.py.
"""
from services.access.service import AccessService

__all__ = ["AccessService"]
