"""VerificationService и приватный SubsumptionChecker для поиска избыточных и поглощённых политик

Наружу — только VerificationService. _subsumption вызывается только из service.py
"""
from services.verification.service import VerificationService

__all__ = ["VerificationService"]
