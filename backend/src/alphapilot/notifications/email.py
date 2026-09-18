"""Small SMTP provider adapter with bounded, sanitized outcomes."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from alphapilot.core.config import Settings, settings
from alphapilot.database.models.notifications import (
    Notification,
    NotificationFailureCategory,
)


@dataclass(frozen=True, slots=True)
class NotificationSendResult:
    delivered: bool
    permanent: bool = False
    failure_category: NotificationFailureCategory | None = None
    provider_message_reference: str | None = None


class NotificationProvider(Protocol):
    def send(self, notification: Notification) -> NotificationSendResult: ...


class SMTPEmailProvider:
    """Send one already-rendered notification; never owns policy or persistence."""

    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def send(self, notification: Notification) -> NotificationSendResult:
        if not self.config.SMTP_HOST or not self.config.NOTIFICATION_FROM_EMAIL:
            return NotificationSendResult(
                delivered=False,
                permanent=True,
                failure_category=NotificationFailureCategory.CONFIGURATION,
            )
        message = EmailMessage()
        message["From"] = self.config.NOTIFICATION_FROM_EMAIL
        message["To"] = notification.recipient
        message["Subject"] = notification.subject
        message["Message-ID"] = f"<{notification.id}@alphapilot.local>"
        message.set_content(notification.body_text)
        if notification.body_html:
            message.add_alternative(notification.body_html, subtype="html")
        try:
            with smtplib.SMTP(
                self.config.SMTP_HOST,
                self.config.SMTP_PORT,
                timeout=self.config.SMTP_TIMEOUT_SECONDS,
            ) as client:
                client.ehlo()
                if self.config.SMTP_USE_TLS:
                    client.starttls()
                    client.ehlo()
                if self.config.SMTP_USERNAME:
                    client.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                refused = client.send_message(message)
                if refused:
                    return NotificationSendResult(
                        delivered=False,
                        permanent=True,
                        failure_category=NotificationFailureCategory.RECIPIENT_REJECTED,
                    )
        except smtplib.SMTPAuthenticationError:
            return NotificationSendResult(
                delivered=False,
                permanent=True,
                failure_category=NotificationFailureCategory.AUTHENTICATION,
            )
        except smtplib.SMTPRecipientsRefused:
            return NotificationSendResult(
                delivered=False,
                permanent=True,
                failure_category=NotificationFailureCategory.RECIPIENT_REJECTED,
            )
        except TimeoutError:
            return NotificationSendResult(
                delivered=False,
                failure_category=NotificationFailureCategory.TIMEOUT,
            )
        except (ConnectionError, OSError, smtplib.SMTPConnectError):
            return NotificationSendResult(
                delivered=False,
                failure_category=NotificationFailureCategory.CONNECTION,
            )
        except smtplib.SMTPException:
            return NotificationSendResult(
                delivered=False,
                failure_category=NotificationFailureCategory.PROVIDER_ERROR,
            )
        return NotificationSendResult(
            delivered=True,
            provider_message_reference=f"<{notification.id}@alphapilot.local>",
        )
