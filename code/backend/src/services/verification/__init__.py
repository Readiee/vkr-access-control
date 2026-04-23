"""VerificationService (DSL §37) + приватный SubsumptionChecker (СВ-4/5).

Наружу экспортируется только VerificationService. _subsumption — приватный
helper, вызывается только из service.py.
"""
from services.verification.service import VerificationService

__all__ = ["VerificationService"]
