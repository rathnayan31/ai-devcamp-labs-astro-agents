"""Cloud DLP redaction of contact details and ID numbers (Lab 3: Govern).

Enabled with PII_REDACTION=on. screening.py runs it on the user's
message before ADK sees it, so raw values never reach Gemini, the session
store or Memory Bank.

Only contact details and ID numbers are redacted. Unlike the lab's Social
Spark agent, PERSON_NAME and locations are left alone: names and birth places
are the substance of an astrology question ("match my kundali with Priya's"),
and the agent selects saved kundalis by name.
"""

from __future__ import annotations

import asyncio
import os

from .gcp import api_url, authorized_session, project_id

INFO_TYPES = (
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD_NUMBER",
    "IBAN_CODE",
    "INDIA_AADHAAR_INDIVIDUAL",
    "INDIA_PAN_INDIVIDUAL",
    "INDIA_PASSPORT",
)
# DLP's PHONE_NUMBER misses the common "98765-43210" spelling, so Indian
# mobiles (10 digits starting 6-9, optional +91/0) also get a pattern.
INDIA_MOBILE = {
    "infoType": {"name": "INDIA_MOBILE_NUMBER"},
    "regex": {"pattern": r"(?:\+91[\s-]?|\b0|\b)[6-9]\d{4}[\s-]?\d{5}\b"},
    "likelihood": "LIKELY",
}


class RedactionUnavailable(RuntimeError):
    """DLP couldn't be reached or answered with an error."""


def pii_redaction_enabled() -> bool:
    return os.environ.get("PII_REDACTION", "").strip().lower() in ("on", "true", "1")


def _deidentify(texts: list[str]) -> list[str]:
    location = os.environ.get("DLP_LOCATION", "us-central1")
    url = api_url(
        "dlp.googleapis.com", f"/v2/projects/{project_id()}/locations/{location}/content:deidentify"
    )
    body = {
        # One request for every text: a table with one row per text.
        "item": {
            "table": {
                "headers": [{"name": "text"}],
                "rows": [{"values": [{"stringValue": t}]} for t in texts],
            }
        },
        "inspectConfig": {
            "infoTypes": [{"name": t} for t in INFO_TYPES],
            "customInfoTypes": [INDIA_MOBILE],
            # A phone number inside a sentence only reaches POSSIBLE.
            "minLikelihood": "POSSIBLE",
        },
        "deidentifyConfig": {
            "infoTypeTransformations": {
                "transformations": [
                    {"primitiveTransformation": {"replaceWithInfoTypeConfig": {}}}
                ]
            }
        },
    }
    try:
        resp = authorized_session().post(url, json=body, timeout=10)
    except Exception as e:  # noqa: BLE001  (network, credentials)
        raise RedactionUnavailable(str(e)) from e
    if resp.status_code != 200:
        raise RedactionUnavailable(f"DLP responded {resp.status_code}: {resp.text[:200]}")
    rows = resp.json()["item"]["table"]["rows"]
    return [row["values"][0].get("stringValue", "") for row in rows]


async def redact_texts(texts: list[str]) -> list[str]:
    """Redact contact details and ID numbers. Raises RedactionUnavailable."""
    if not pii_redaction_enabled() or not any(t.strip() for t in texts):
        return texts
    return await asyncio.to_thread(_deidentify, texts)
