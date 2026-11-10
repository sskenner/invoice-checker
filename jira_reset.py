"""Demo reset: delete every ticket that jira_sync.py created, so the demo can run fresh.

    python jira_reset.py          asks you to type yes first
    python jira_reset.py --yes    no prompt (the teleprompter button confirms in the browser)
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

URL = os.environ["JIRA_URL"].rstrip("/")
AUTH = base64.b64encode(
    f"{os.environ['JIRA_EMAIL']}:{os.environ['JIRA_API_TOKEN']}".encode()).decode()
KEY = os.environ.get("JIRA_PROJECT_KEY", "KAN")
HEADERS = {"Authorization": f"Basic {AUTH}", "Accept": "application/json",
           "Content-Type": "application/json"}


def call(method, path, body=None):
    req = urllib.request.Request(URL + path, method=method, headers=HEADERS,
                                 data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Jira said {err.code}: {err.read().decode()[:500]}")


def main():
    found = call("POST", "/rest/api/3/search/jql",
                 {"jql": f"project = {KEY} AND labels = invoice-checker",
                  "maxResults": 100, "fields": ["summary"]})
    issues = found.get("issues", [])
    if not issues:
        raise SystemExit("Nothing to delete.")

    for i in issues:
        print(f"  {i['key']}  {i['fields']['summary']}")
    if "--yes" not in sys.argv:
        answer = input(f"\nPermanently delete these {len(issues)} ticket(s)? Type yes: ")
        if answer.strip().lower() != "yes":
            raise SystemExit("Cancelled. Nothing deleted.")

    for i in issues:
        call("DELETE", f"/rest/api/3/issue/{i['key']}")
        print(f"  deleted {i['key']}")


if __name__ == "__main__":
    main()
