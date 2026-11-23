"""Email notification adapter. ``console`` mode logs messages (development only); ``smtp`` sends them."""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)


@dataclass
class Email:
    to: str
    subject: str
    text: str


# In console mode the last messages are kept in memory so tests and local tooling can inspect them.
console_outbox: list[Email] = []


def _send_smtp(msg: Email) -> None:
    s = get_settings()
    em = EmailMessage()
    em["From"], em["To"], em["Subject"] = s.email_from, msg.to, msg.subject
    em.set_content(msg.text)
    with smtplib.SMTP(s.smtp_host or "localhost", s.smtp_port, timeout=15) as smtp:
        if s.smtp_starttls:
            smtp.starttls()
        if s.smtp_username:
            smtp.login(s.smtp_username, s.smtp_password or "")
        smtp.send_message(em)


async def send_email(msg: Email) -> None:
    if get_settings().email_mode == "console":
        console_outbox.append(msg)
        del console_outbox[:-100]
        # The body (which contains one-time links) is printed only in local/test console mode.
        print(f"\n--- EMAIL (console mode) ---\nTo: {msg.to}\nSubject: {msg.subject}\n\n{msg.text}\n---\n")  # noqa: T201
        return
    await asyncio.to_thread(_send_smtp, msg)
    log.info("email_sent", subject=msg.subject)
