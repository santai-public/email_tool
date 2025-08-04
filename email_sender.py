from __future__ import annotations

from typing import List
import os
import imaplib
from email.mime.text import MIMEText

import boto3


class EmailProvider:
    """Abstract base email provider."""

    def send_email(self, from_addr: str, to_addrs: List[str], subject: str, body: str) -> None:
        raise NotImplementedError


class SESEmailProvider(EmailProvider):
    """Send email using Amazon SES."""

    def __init__(self, region_name: str | None = None):
        region = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.client = boto3.client("ses", region_name=region)

    def send_email(self, from_addr: str, to_addrs: List[str], subject: str, body: str) -> None:
        self.client.send_email(
            Source=from_addr,
            Destination={"ToAddresses": list(to_addrs)},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )


class IMAPEmailProvider(EmailProvider):
    """Send email by appending the message to a mailbox via IMAP."""

    def __init__(self, server: str, username: str, password: str, mailbox: str = "INBOX"):
        self.server = server
        self.username = username
        self.password = password
        self.mailbox = mailbox

    def send_email(self, from_addr: str, to_addrs: List[str], subject: str, body: str) -> None:
        msg = MIMEText(body)
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg["Subject"] = subject

        with imaplib.IMAP4_SSL(self.server) as imap:
            imap.login(self.username, self.password)
            imap.append(self.mailbox, None, None, msg.as_bytes())
            imap.logout()


class EmailSender:
    """Factory class to send email using a chosen provider."""

    def __init__(self, provider: str, **kwargs):
        provider = provider.lower()
        if provider == "ses":
            self.provider: EmailProvider = SESEmailProvider(kwargs.get("region_name"))
        elif provider == "imap":
            required = {"server", "username", "password"}
            missing = required - kwargs.keys()
            if missing:
                raise ValueError(f"Missing IMAP config keys: {', '.join(sorted(missing))}")
            self.provider = IMAPEmailProvider(
                kwargs["server"],
                kwargs["username"],
                kwargs["password"],
                kwargs.get("mailbox", "INBOX"),
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def send_email(self, from_addr: str, to_addrs: List[str], subject: str, body: str) -> None:
        self.provider.send_email(from_addr, to_addrs, subject, body)
