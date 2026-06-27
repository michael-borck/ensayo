"""Email provider dispatch (console / smtp / resend)."""

from __future__ import annotations

import pytest

from ensayo.api import email


def test_default_provider_is_console_and_not_configured(monkeypatch):
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert email.provider() == "console"
    assert email.configured() is False


def test_smtp_configured_when_host_set(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    assert email.configured() is True
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert email.configured() is False


def test_resend_configured_when_key_set(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    assert email.configured() is True
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert email.configured() is False


def test_console_send_returns_true(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    assert email.send_email("x@example.com", "subj", "body") is True


def test_smtp_without_host_returns_false(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert email.send_email("x@example.com", "subj", "body") is False


def test_resend_send_posts_and_returns_true(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("RESEND_FROM", "Ensayo <noreply@app.dev>")

    calls = {}

    class _Resp:
        status_code = 202

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        return _Resp()

    monkeypatch.setattr(email.httpx, "post", fake_post)
    assert email.send_email("lec@curtin.edu.au", "Your code", "CODE1234") is True
    assert calls["url"] == "https://api.resend.com/emails"
    assert calls["headers"]["Authorization"] == "Bearer re_test"
    assert calls["json"]["to"] == ["lec@curtin.edu.au"]
    assert calls["json"]["subject"] == "Your code"


def test_resend_send_without_key_returns_false(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    # must not attempt a network call
    monkeypatch.setattr(email.httpx, "post",
                        lambda *a, **k: pytest.fail("should not call Resend without a key"))
    assert email.send_email("x@example.com", "s", "b") is False


def test_unknown_provider_falls_back_to_console(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "nonsense")
    assert email.send_email("x@example.com", "s", "b") is True  # console path
