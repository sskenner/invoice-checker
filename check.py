"""Step 4: Check each extracted invoice against the company's own records.

No AI here - plain rules, so the same invoice always gets the same answer
and every flag comes with a clear reason.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path("data")
EXTRACTED = Path("extracted")
RESULTS = Path("results.json")

def load_pos_from_csv():
    """What was ordered, from the local CSV (works offline)."""
    po_lines = {}       # (po_number, item_code) -> PO line
    po_vendor = {}      # po_number -> vendor name
    with (DATA / "purchase_orders.csv").open() as f:
        for row in csv.DictReader(f):
            po_lines[(row["po_number"], row["item_code"])] = {
                "qty_ordered": float(row["qty_ordered"]),
                "unit_price": float(row["unit_price"]),
            }
            po_vendor[row["po_number"]] = row["vendor"]
    return po_lines, po_vendor


def load_pos_from_procore():
    """What was ordered, from the purchase orders in Procore (the system of record).
    Each line's description starts with its item code: 'LUM-2408 | 2x4x8 SPF stud'."""
    from procore_api import po_lines as procore_lines, purchase_orders
    po_lines, po_vendor = {}, {}
    for po in purchase_orders():
        po_vendor[po["number"]] = po["vendor"]["company"]
        for line in procore_lines(po["id"]):
            code = line["description"].split("|")[0].strip()
            po_lines[(po["number"], code)] = {
                "qty_ordered": float(line["quantity"]),
                "unit_price": float(line["unit_cost"]),
            }
    print(f"Loaded {len(po_vendor)} purchase orders ({len(po_lines)} lines) from Procore")
    return po_lines, po_vendor


def load_records(source="csv"):
    """Load what was ordered and what was received, keyed for fast lookup."""
    po_lines, po_vendor = load_pos_from_procore() if source == "procore" else load_pos_from_csv()

    received = defaultdict(float)  # (po_number, item_code) -> total qty received
    with (DATA / "deliveries.csv").open() as f:
        for row in csv.DictReader(f):
            received[(row["po_number"], row["item_code"])] += float(row["qty_received"])

    return po_lines, po_vendor, received

def same_amount(a: float, b: float) -> bool:
    """Compare dollar amounts to the cent (avoids floating-point surprises)."""
    return abs(a - b) < 0.005

def normalize(name: str) -> str:
    """'EMPIRE ELECTRICAL DISTRIBUTORS' and 'Empire Electrical Distributors' are the same vendor."""
    return " ".join(name.lower().split())

def check_invoice(inv, po_lines, po_vendor, received, seen_invoices):
    """Return a list of (team, problem) pairs. An empty list means approve."""
    issues = []
    po = inv["po_number"]

    # 1. Is this invoice a duplicate of one we've already processed?
    key = (normalize(inv["vendor_name"]), inv["invoice_number"])
    if key in seen_invoices:
        issues.append(("Accounting", f"Duplicate of invoice {inv['invoice_number']}, already received on {seen_invoices[key]}"))
        return issues  # no point checking the rest - don't pay it twice
    seen_invoices[key] = inv["invoice_date"]

    # 2. Does the PO exist, and is it from this vendor?
    if po not in po_vendor:
        issues.append(("Purchasing", f"PO number {po!r} not found in our records"))
        return issues
    if normalize(po_vendor[po]) != normalize(inv["vendor_name"]):
        issues.append(("Purchasing", f"{po} belongs to {po_vendor[po]}, not {inv['vendor_name']}"))

    # 3. Check every line against the PO and the delivery tickets.
    for line in inv["line_items"]:
        code = line["item_code"]
        po_line = po_lines.get((po, code))
        if po_line is None:
            issues.append(("Purchasing", f"{code} is not on {po}"))
            continue

        if not same_amount(line["unit_price"], po_line["unit_price"]):
            diff = (line["unit_price"] - po_line["unit_price"]) * line["quantity"]
            issues.append(("Purchasing", f"{code}: billed ${line['unit_price']:,.2f}/unit, PO price is ${po_line['unit_price']:,.2f} (${diff:,.2f} over)"))

        if line["quantity"] > po_line["qty_ordered"]:
            issues.append(("Purchasing", f"{code}: billed {line['quantity']:g}, only {po_line['qty_ordered']:g} ordered"))

        got = received[(po, code)]
        if line["quantity"] > got:
            issues.append(("Logistics", f"{code}: billed {line['quantity']:g}, only {got:g} delivered"))

        if not same_amount(line["quantity"] * line["unit_price"], line["line_total"]):
            issues.append(("Accounting", f"{code}: {line['quantity']:g} x ${line['unit_price']:,.2f} does not equal the line total ${line['line_total']:,.2f}"))

    # 4. Do the lines add up to what the vendor is asking for?
    lines_sum = sum(line["line_total"] for line in inv["line_items"])
    expected_total = lines_sum + inv["tax"]
    if not same_amount(expected_total, inv["total_due"]):
        issues.append(("Accounting", f"Lines + tax add up to ${expected_total:,.2f}, but invoice asks for ${inv['total_due']:,.2f}"))

    return issues

def main():
    # python check.py                  -> POs from data/purchase_orders.csv
    # python check.py --source procore -> POs from Procore (deliveries stay in the CSV)
    source = "procore" if "procore" in sys.argv[1:] else "csv"
    po_lines, po_vendor, received = load_records(source)

    invoices = []
    for path in EXTRACTED.glob("*.json"):
        inv = json.loads(path.read_text())
        inv["source_file"] = path.stem + ".pdf"
        invoices.append(inv)
    # Oldest first, so the original is processed before any re-sent copy.
    invoices.sort(key=lambda inv: inv["invoice_date"])

    seen_invoices = {}
    results = []
    for inv in invoices:
        issues = check_invoice(inv, po_lines, po_vendor, received, seen_invoices)
        teams = sorted({team for team, _ in issues})
        status = "Approved" if not issues else "Needs review: " + ", ".join(teams)

        print(f"\n{inv['source_file']}  ({inv['vendor_name']}, ${inv['total_due']:,.2f})")
        print(f"  -> {status}")
        for team, problem in issues:
            print(f"     [{team}] {problem}")

        results.append({
            "file": inv["source_file"],
            "vendor": inv["vendor_name"],
            "invoice_number": inv["invoice_number"],
            "invoice_date": inv["invoice_date"],
            "po_number": inv["po_number"],
            "total_due": inv["total_due"],
            "status": "approved" if not issues else "review",
            "teams": teams,
            "issues": [{"team": t, "problem": p} for t, p in issues],
        })

    RESULTS.write_text(json.dumps(results, indent=2))
    print(f"\nSaved {RESULTS}")


if __name__ == "__main__":
    main()
