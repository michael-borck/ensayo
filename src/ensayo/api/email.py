"""Email delivery — provider switch (console / smtp / resend).

All outbound mail (verification codes, password resets) goes through
``send_email``. The provider is chosen with ``EMAIL_PROVIDER``:

* ``console`` (default) — logs to stdout, returns True. Dev only; on the server,
  codes are surfaced in the dashboard admin panel for hand-relay.
* ``smtp`` — ``SMTP_HOST/PORT/USER/PASSWORD/FROM`` (starttls). Works for Gmail,
  SendGrid, Brevo, Resend-SMTP, or an institutional relay.
* ``resend`` — Resend REST API (``RESEND_API_KEY`` + ``RESEND_FROM``). Most
  reliable for a public demo; the free tier covers thousands of messages.

A single ``EMAIL_FROM`` is honoured by smtp/resend when their specific var is
unset, so one address can serve every provider.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

import httpx

logger = logging.getLogger("ensayo.api")


def _from(default: str = "ensayo@localhost") -> str:
    return (os.environ.get("EMAIL_FROM")
            or os.environ.get("SMTP_FROM")
            or os.environ.get("RESEND_FROM")
            or os.environ.get("SMTP_USER")
            or default)


def provider() -> str:
    return os.environ.get("EMAIL_PROVIDER", "console").strip().lower()


def configured() -> bool:
    """True if a real (non-console) provider is wired with its credentials."""
    p = provider()
    if p == "smtp":
        return bool(os.environ.get("SMTP_HOST"))
    if p == "resend":
        return bool(os.environ.get("RESEND_API_KEY"))
    return False  # console / unknown


def send_email(to: str, subject: str, body: str) -> bool:
    """Deliver an email via the configured provider. False on failure/no creds."""
    p = provider()
    if p == "smtp":
        return _smtp(to, subject, body)
    if p == "resend":
        return _resend(to, subject, body)
    return _console(to, subject, body)  # default / dev


def _console(to: str, subject: str, body: str) -> bool:
    print(f"[ensayo email] to={to} subject={subject!r}\n{body}\n")
    return True


def _smtp(to: str, subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    msg = EmailMessage()
    msg["From"] = _from()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        use_ssl = os.environ.get("SMTP_SSL", "").lower() in ("1", "true", "yes")
        smtp = smtplib.SMTP_SSL(host, port, timeout=20) if use_ssl else smtplib.SMTP(host, port, timeout=20)
        with smtp:
            if not use_ssl:
                smtp.starttls()
            user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
            if user and pw:
                smtp.login(user, pw)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("smtp email to %s failed: %s", to, exc)
        return False


def _resend(to: str, subject: str, body: str) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        return False
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            json={"from": _from(), "to": [to], "subject": subject, "text": body},
            timeout=20,
        )
        return r.status_code in (200, 202)
    except httpx.HTTPError as exc:
        logger.warning("resend email to %s failed: %s", to, exc)
        return False
