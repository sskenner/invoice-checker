"""Step 5: Turn results.json into a dashboard page each team can use."""
import html
import json
import os
import webbrowser
from datetime import datetime
from pathlib import Path

RESULTS = Path("results.json")
OUTPUT = Path("dashboard.html")
TEAMS = ["Purchasing", "Logistics", "Accounting"]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Invoice Review</title>
<style>
  :root {
    --bg: #fcfcfb; --card: #ffffff; --ink: #1a1a19; --muted: #6b6b66;
    --line: #e6e5e0; --chip: #f1f0ec; --good: #0ca30c; --warn: #fab219;
    --accent: #2f5bd3;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #1a1a19; --card: #232322; --ink: #f0efea; --muted: #a3a29c;
      --line: #3a3a37; --chip: #2e2e2c; --accent: #8aa8ff;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  main { max-width: 960px; margin: 0 auto; padding: 32px 16px 64px; }
  h1 { font-size: 24px; margin: 0; }
  .sub { color: var(--muted); margin: 4px 0 24px; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  .tile { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px; }
  .tile .label { color: var(--muted); font-size: 13px; }
  .tile .value { font-size: 28px; font-weight: 600; }
  .tile .note { color: var(--muted); font-size: 13px; }
  .filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 28px 0 12px; }
  .filters button {
    font: inherit; font-size: 14px; color: var(--ink); background: var(--card);
    border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; cursor: pointer;
  }
  .filters button[aria-pressed="true"] { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
  .invoice {
    background: var(--card); border: 1px solid var(--line); border-radius: 10px;
    padding: 14px 16px; margin-bottom: 10px;
  }
  .row { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; }
  .vendor { font-weight: 600; }
  .meta { color: var(--muted); font-size: 13px; }
  .amount { font-weight: 600; font-variant-numeric: tabular-nums; }
  .status { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; margin-top: 6px; }
  .dot { width: 18px; height: 18px; border-radius: 50%; display: inline-grid; place-items: center;
         font-size: 12px; font-weight: 700; color: #1a1a19; }
  .dot.good { background: var(--good); color: #fff; }
  .dot.warn { background: var(--warn); }
  ul { margin: 8px 0 0; padding: 0; list-style: none; }
  li { display: flex; gap: 10px; align-items: baseline; padding: 4px 0; border-top: 1px solid var(--line); }
  .team { background: var(--chip); border-radius: 6px; padding: 1px 8px; font-size: 12px;
          font-weight: 600; white-space: nowrap; }
</style>
</head>
<body>
<main>
  <h1>Invoice review</h1>
  <p class="sub">Checked against purchase orders and delivery tickets &middot; __GENERATED__</p>
  <section class="tiles">__TILES__</section>
  <nav class="filters" aria-label="Filter by team">__FILTERS__</nav>
  <section id="list">__INVOICES__</section>
</main>
<script>
  const buttons = document.querySelectorAll(".filters button");
  buttons.forEach(btn => btn.addEventListener("click", () => {
    buttons.forEach(b => b.setAttribute("aria-pressed", b === btn));
    const pick = btn.dataset.filter;
    document.querySelectorAll(".invoice").forEach(card => {
      const tags = card.dataset.tags.split(" ");
      card.hidden = !(pick === "all" || tags.includes(pick));
    });
  }));
</script>
</body>
</html>
"""


def money(x: float) -> str:
    return f"${x:,.2f}"


def tile(label: str, value: str, note: str) -> str:
    return (f'<div class="tile"><div class="label">{label}</div>'
            f'<div class="value">{value}</div><div class="note">{note}</div></div>')


def invoice_card(r: dict) -> str:
    e = html.escape  # text from PDFs is treated as text, never as HTML
    tags = ["approved"] if r["status"] == "approved" else r["teams"]

    if r["status"] == "approved":
        status = '<span class="dot good">&#10003;</span> Approved for payment'
    else:
        status = f'<span class="dot warn">!</span> Needs review: {e(", ".join(r["teams"]))}'

    issues = "".join(
        f'<li><span class="team">{e(i["team"])}</span><span>{e(i["problem"])}</span></li>'
        for i in r["issues"]
    )
    return f"""
    <article class="invoice" data-tags="{e(' '.join(tags))}">
      <div class="row">
        <span class="vendor">{e(r["vendor"].title())}</span>
        <span class="amount">{money(r["total_due"])}</span>
      </div>
      <div class="meta">Invoice {e(r["invoice_number"])} &middot; {e(r["po_number"] or "no PO")}
        &middot; {e(r["invoice_date"])} &middot; {e(r["file"])}</div>
      <div class="status">{status}</div>
      {f"<ul>{issues}</ul>" if issues else ""}
    </article>"""


def main():
    results = json.loads(RESULTS.read_text())

    approved = [r for r in results if r["status"] == "approved"]
    held = [r for r in results if r["status"] != "approved"]
    tiles = (
        tile("Invoices checked", str(len(results)), "from the invoices folder")
        + tile("Approved to pay", money(sum(r["total_due"] for r in approved)),
               f"{len(approved)} invoice(s), all checks passed")
        + tile("On hold", money(sum(r["total_due"] for r in held)),
               f"{len(held)} invoice(s) waiting on a team")
    )

    def count(team):
        return sum(team in r["teams"] for r in results)

    filters = '<button data-filter="all" aria-pressed="true">All ({})</button>'.format(len(results))
    filters += "".join(
        f'<button data-filter="{t}" aria-pressed="false">{t} ({count(t)})</button>' for t in TEAMS
    )
    filters += f'<button data-filter="approved" aria-pressed="false">Approved ({len(approved)})</button>'

    # Problems first, so the page opens on what needs attention.
    ordered = held + approved
    page = (PAGE
            .replace("__GENERATED__", datetime.now().strftime("%b %d, %Y %I:%M %p"))
            .replace("__TILES__", tiles)
            .replace("__FILTERS__", filters)
            .replace("__INVOICES__", "".join(invoice_card(r) for r in ordered)))

    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    # The teleprompter sets NO_BROWSER and opens the page itself.
    if not os.environ.get("NO_BROWSER"):
        webbrowser.open(OUTPUT.resolve().as_uri())


if __name__ == "__main__":
    main()
