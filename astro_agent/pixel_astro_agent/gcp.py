"""Authenticated calls to Google APIs from inside the agent (DLP, Model Armor).

On Agent Runtime the agent identity's tokens are bound to its workload
certificate: they're only accepted over mTLS, on the ``*.mtls.googleapis.com``
endpoints. Plain HTTPS with the same token gets 401 (the lab's "works locally,
401 when deployed"). Locally there's no workload certificate, so ADC is used
over plain HTTPS.
"""

from __future__ import annotations

import os

_session = None


def project_id() -> str:
    """Project ID, not number: DLP rejects a number ("Malformed parent field")."""
    return os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")


def authorized_session():
    global _session
    if _session is None:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        session = AuthorizedSession(credentials)
        session.configure_mtls_channel()
        _session = session
    return _session


def api_url(host: str, path: str) -> str:
    """``host`` like "dlp.googleapis.com", switched to its mTLS twin when needed."""
    if authorized_session().is_mtls:
        host = host.replace(".googleapis.com", ".mtls.googleapis.com")
    return f"https://{host}{path}"
