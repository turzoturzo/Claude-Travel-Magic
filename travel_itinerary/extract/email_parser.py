"""Email content extraction — refactored from travel_sorter.py EmailParser."""

import hashlib
import mailbox
from email.header import decode_header
from typing import Any, Dict

from bs4 import BeautifulSoup


def decode_str(s: str) -> str:
    if not s:
        return ""
    decoded = decode_header(s)
    parts = []
    for part, encoding in decoded:
        if isinstance(part, bytes):
            try:
                parts.append(part.decode(encoding or "utf-8", errors="ignore"))
            except Exception:
                parts.append(part.decode("utf-8", errors="ignore"))
        else:
            parts.append(str(part))
    return "".join(parts)


def extract_content(msg: mailbox.Message) -> Dict[str, Any]:
    """Extract subject, from, body, date, and message_id from a mailbox message."""
    subject = decode_str(msg.get("subject", ""))
    from_header = decode_str(msg.get("from", ""))
    date_header = msg.get("date", "")
    message_id = msg.get("Message-ID", "") or msg.get("Message-Id", "") or ""

    body_text = ""
    html_content = ""

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                p = part.get_payload(decode=True)
                if p:
                    body_text += p.decode(errors="ignore")
            elif ct == "text/html":
                p = part.get_payload(decode=True)
                if p:
                    html_content += p.decode(errors="ignore")
    else:
        p = msg.get_payload(decode=True)
        if p:
            if msg.get_content_type() == "text/html":
                html_content = p.decode(errors="ignore")
            else:
                body_text = p.decode(errors="ignore")

    if html_content and not body_text:
        soup = BeautifulSoup(html_content, "html.parser")
        for s in soup(["script", "style"]):
            s.decompose()
        body_text = soup.get_text(separator=" ", strip=True)

    return {
        "subject": subject,
        "from": from_header,
        "body": body_text,
        "date": date_header,
        "message_id": message_id,
    }


def email_hash(content: Dict[str, Any]) -> str:
    """Stable hash for an email based on subject + date + from."""
    key = f"{content.get('subject', '')}|{content.get('date', '')}|{content.get('from', '')}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()
