#!/usr/bin/env python3
"""Check CDN for new version by comparing Last-Modified headers."""

import json
from pathlib import Path
import requests

STATE_FILE = Path(__file__).parent / "state.json"

def check_cdn_version() -> str:
    """Check if CDN has updates, return version if changed, else 'no_change'."""
    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        return "no_change"

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    session.headers["Accept-Encoding"] = "identity"

    changes = {}
    for key in ["manual", "addon-sdk", "game-services"]:
        url = state.get("cdn_urls", {}).get(key)
        if not url:
            continue

        try:
            resp = session.head(url, allow_redirects=True, timeout=30)
            if resp.status_code == 200:
                last_modified = resp.headers.get("Last-Modified", "")
                stored_lm = state.get("cdn_last_modified", {}).get(key)
                if stored_lm != last_modified:
                    changes[key] = True
        except Exception:
            pass

    if changes:
        return state.get("construct_version", "unknown")
    else:
        return "no_change"

if __name__ == "__main__":
    print(check_cdn_version())
