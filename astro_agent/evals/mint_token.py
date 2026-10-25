"""Mint the eval test user's MCP token without the Node server checkout (CI).

    AGENT_MCP_JWT_SECRET=... uv run python evals/mint_token.py <user_id> [--ttl 3600]

Mirrors the Pixel Astro server's utils/agentMcpToken.js: an HS256 JWT signed
with a key derived from the secret (HMAC-SHA256 of "pixel-astro-agent-mcp:v1"),
audience-bound to the MCP endpoint, scope agent_mcp:read, short-lived. The
server's verifyAgentMcpToken accepts it; if the server changes its scheme,
run.sh's minting with scripts/mintAgentMcpToken.js remains the reference.
Prints the token to stdout only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time

AUDIENCE = "pixel-astro-agent-mcp"
SCOPE = "agent_mcp:read"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def mint(user_id: str, secret: str, ttl: int) -> str:
    key = hmac.new(secret.encode(), f"{AUDIENCE}:v1".encode(), hashlib.sha256).hexdigest().encode()
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {"sub": user_id, "scope": SCOPE, "iat": now, "exp": now + ttl, "aud": AUDIENCE}
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = _b64(hmac.new(key, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("user_id")
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    secret = os.environ.get("AGENT_MCP_JWT_SECRET") or os.environ.get("JWT_SECRET")
    if not secret:
        sys.exit("Set AGENT_MCP_JWT_SECRET (the Pixel Astro server's AGENT_MCP_JWT_SECRET or JWT_SECRET).")
    print(mint(args.user_id, secret, args.ttl))


if __name__ == "__main__":
    main()
