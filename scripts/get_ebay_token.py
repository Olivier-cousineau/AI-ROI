"""Fetch and cache an eBay OAuth token for the Browse API."""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests


LOGGER = logging.getLogger(__name__)
TOKEN_ENDPOINT = "https://api.ebay.com/identity/v1/oauth2/token"
SCOPE = "https://api.ebay.com/oauth/api_scope"
CACHE_PATH = Path(".cache/ebay_token.json")


def _load_credentials() -> tuple[str | None, str | None]:
    return os.getenv("EBAY_CLIENT_ID"), os.getenv("EBAY_CLIENT_SECRET")


def _encode_basic_auth(client_id: str, client_secret: str) -> str:
    token = f"{client_id}:{client_secret}".encode("utf-8")
    return base64.b64encode(token).decode("utf-8")


def _write_cache(access_token: str, expires_at: int) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"access_token": access_token, "expires_at": expires_at}
    CACHE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def fetch_token() -> dict[str, object] | None:
    """Return token payload from eBay or None if unavailable."""
    client_id, client_secret = _load_credentials()
    if not client_id or not client_secret:
        LOGGER.warning("Missing EBAY_CLIENT_ID/EBAY_CLIENT_SECRET; skipping token fetch.")
        return None

    auth_header = _encode_basic_auth(client_id, client_secret)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }
    data = {"grant_type": "client_credentials", "scope": SCOPE}
    try:
        response = requests.post(TOKEN_ENDPOINT, headers=headers, data=data, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        LOGGER.warning("Failed to fetch eBay OAuth token: %s", exc)
        return None
    except ValueError as exc:
        LOGGER.warning("Failed to parse eBay OAuth token response: %s", exc)
        return None

    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in")
    if not access_token or not expires_in:
        LOGGER.warning("eBay OAuth response missing access_token/expires_in.")
        return None

    try:
        expires_at = int(time.time()) + int(expires_in)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid expires_in value in eBay OAuth response.")
        return None

    _write_cache(access_token, expires_at)
    return {"access_token": access_token, "expires_in": expires_in}


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    payload = fetch_token()
    if payload:
        print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
