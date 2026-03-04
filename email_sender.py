"""
email_sender.py – Builds mailto links with pre-filled subject & body.
No SMTP configuration needed.
"""
import urllib.parse


def render_template(text: str, variables: dict) -> str:
    """Replace {variable} placeholders in text with actual values."""
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def build_mailto_link(to_email: str, subject: str, body: str) -> str:
    """
    Build a mailto: URL with pre-filled subject and body.
    Opens the user's default email client.
    """
    params = urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    return f"mailto:{to_email}?{params}"
