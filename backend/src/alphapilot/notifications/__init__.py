"""Operational notification provider boundary."""

from .email import NotificationSendResult, SMTPEmailProvider

__all__ = ["NotificationSendResult", "SMTPEmailProvider"]
