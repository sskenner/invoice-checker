"""Step 3: Turn each held invoice in results.json into a Jira ticket for its team."""
import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

URL = os.environ["JIRA_URL"].rstrip("/")
EMAIL = os.environ["JIRA_EMAIL"]
TOKEN = os.environ["JIRA_API_TOKEN"]
KEY = os.environ.get("JIRA_PROJECT_KEY", "KAN")
AUTH = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()

RESULTS = Path("results.json")


def jira(method, path, body=None):
    """Call the Jira REST API and return the JSON reply."""
    req = urllib.request.Request(
        URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Basic {AUTH}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Jira said {err.code}: {err.read().decode()[:500]}")


def source_label(filename):
    """One label per PDF, so re-running never creates a second ticket."""
    return "src-" + re.sub(r"[^A-Za-z0-9_-]", "_", Path(filename).stem)


def already_filed(label):
    found = jira("POST", "/rest/api/3/search/jql",
                 {"jql": f'project = {KEY} AND labels = "{label}"',
                  "maxResults": 1, "fields": ["summary"]})
    return found["issues"][0]["key"] if found.get("issues") else None


def text(s):
    return {"type": "text", "text": s}


def description(r):
    """Jira's description format: a short summary, then one bullet per problem."""
    bullets = [
        {"type": "listItem", "content": [{"type": "paragraph", "content": [
            text(f"{i['team']}: {i['problem']}")]}]}
        for i in r["issues"]
    ]
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [text(
            f"{r['vendor'].title()} invoice {r['invoice_number']} for ${r['total_due']:,.2f} "
            f"is on hold. PO {r['po_number'] or 'none'}, dated {r['invoice_date']}.")]},
        {"type": "bulletList", "content": bullets},
        {"type": "paragraph", "content": [text(f"Source file: {r['file']}")]},
    ]}


def main():
    results = json.loads(RESULTS.read_text())
    held = [r for r in results if r["status"] != "approved"]
    print(f"{len(held)} held invoice(s) to file in {KEY}\n")

    for r in held:
        label = source_label(r["file"])
        existing = already_filed(label)
        if existing:
            print(f"  skip   {existing}  {r['file']} (already filed)")
            continue

        teams = " + ".join(r["teams"])
        fields = {
            "project": {"key": KEY},
            "issuetype": {"name": "Task"},
            "summary": f"[{teams}] {r['vendor'].title()} {r['invoice_number']}: "
                       f"${r['total_due']:,.2f} on hold",
            "description": description(r),
            "labels": [t.lower() for t in r["teams"]] + ["invoice-checker", label],
        }
        created = jira("POST", "/rest/api/3/issue", {"fields": fields})
        print(f"  created {created['key']}  {fields['summary']}")
        print(f"          {URL}/browse/{created['key']}")


if __name__ == "__main__":
    main()