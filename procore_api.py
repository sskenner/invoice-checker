"""Shared Procore helpers: log in once, then get/post/delete with the right headers.

Uses the Developer Sandbox by default. Settings come from environment variables
(set once with setx, never typed into code):
    PROCORE_CLIENT_ID, PROCORE_CLIENT_SECRET, PROCORE_COMPANY_ID
    PROCORE_PROJECT_ID   optional, default 379257 (Sandbox Test Project)
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

LOGIN = os.environ.get("PROCORE_LOGIN_URL", "https://login-sandbox.procore.com").rstrip("/")
API = os.environ.get("PROCORE_API_URL", "https://sandbox.procore.com").rstrip("/")
COMPANY = os.environ["PROCORE_COMPANY_ID"]
PROJECT = os.environ.get("PROCORE_PROJECT_ID", "379257")

_token = None


def token():
    """Log in as the app's service account (no browser needed). Cached for this run."""
    global _token
    if _token is None:
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": os.environ["PROCORE_CLIENT_ID"],
            "client_secret": os.environ["PROCORE_CLIENT_SECRET"],
        }).encode()
        req = urllib.request.Request(LOGIN + "/oauth/token", data=body, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req) as resp:
            _token = json.load(resp)["access_token"]
    return _token


MAX_WAIT = 90   # seconds we're willing to wait for a rate limit to reset


def call(method, path, body=None):
    """One Procore API call. Waits and retries if Procore says we're going too fast;
    stops with Procore's own error message for anything else."""
    for attempt in range(4):
        req = urllib.request.Request(
            API + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token()}",
                     "Procore-Company-Id": COMPANY,        # required for service accounts
                     "Accept": "application/json",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 3:
                wait = _rate_limit_wait(err.headers)
                if wait <= MAX_WAIT:
                    print(f"  (Procore rate limit: waiting {wait:.0f}s, then retrying)")
                    time.sleep(wait)
                    continue
                raise SystemExit(f"Procore rate limit: it resets in about {wait / 60:.0f} min. "
                                 "Run this again after that.")
            raise SystemExit(f"Procore said {err.code} on {method} {path.split('?')[0]}: "
                             f"{err.read().decode()[:500]}")


def _rate_limit_wait(headers):
    """Seconds until Procore's rate limit resets (from Retry-After or X-Rate-Limit-Reset)."""
    if headers.get("Retry-After", "").isdigit():
        return float(headers["Retry-After"])
    reset = headers.get("X-Rate-Limit-Reset", "")
    if reset.isdigit():
        return max(1.0, int(reset) - time.time() + 1)
    return 30.0


def get_all(path):
    """GET a list, following Procore's pages (100 per page)."""
    sep = "&" if "?" in path else "?"
    items, page = [], 1
    while True:
        batch = call("GET", f"{path}{sep}page={page}&per_page=100")
        items += batch
        if len(batch) < 100:
            return items
        page += 1


def purchase_orders():
    """All purchase order contracts on the demo project."""
    return get_all(f"/rest/v1.0/purchase_order_contracts?project_id={PROJECT}")


def po_lines(po_id):
    """Line items of one purchase order."""
    return get_all(f"/rest/v1.0/purchase_order_contracts/{po_id}/line_items?project_id={PROJECT}")
