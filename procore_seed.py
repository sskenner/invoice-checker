"""Procore step 2: put the demo's purchase orders into the Procore sandbox.

Reads data/purchase_orders.csv and creates, in the demo project:
  - each vendor (in the company directory, if it isn't there yet)
  - each PO as an Approved purchase order contract
  - each PO line, with the item code at the start of the description,
    e.g. "LUM-2408 | 2x4x8 SPF stud", so check.py can match lines exactly.
Anything that already exists is skipped, so it's safe to run again.
"""
import csv
from collections import defaultdict
from pathlib import Path

from procore_api import COMPANY, PROJECT, call, get_all, po_lines, purchase_orders

CSV = Path("data/purchase_orders.csv")


def load_csv():
    pos = defaultdict(lambda: {"vendor": None, "lines": []})
    with CSV.open() as f:
        for row in csv.DictReader(f):
            po = pos[row["po_number"]]
            po["vendor"] = row["vendor"]
            po["lines"].append(row)
    return pos


def vendor_ids(names):
    """Find each vendor in the company directory, creating it if missing."""
    existing = {v["name"]: v["id"] for v in get_all(f"/rest/v1.0/vendors?company_id={COMPANY}")}
    ids = {}
    for name in sorted(names):
        if name in existing:
            print(f"  vendor exists: {name}")
            ids[name] = existing[name]
        else:
            v = call("POST", "/rest/v1.0/vendors",
                     {"company_id": int(COMPANY), "vendor": {"name": name, "is_active": True}})
            print(f"  vendor created: {name}")
            ids[name] = v["id"]

    # A PO can only use a vendor that has been added to the project.
    on_project = {v["id"] for v in get_all(f"/rest/v1.1/projects/{PROJECT}/vendors")}
    for name, vid in ids.items():
        if vid not in on_project:
            call("POST", f"/rest/v1.1/projects/{PROJECT}/vendors/{vid}/actions/add", {})
            print(f"  added to project: {name}")
    return ids


def main():
    pos = load_csv()
    print(f"Project {PROJECT}: seeding {len(pos)} purchase orders from {CSV}")
    vids = vendor_ids({po["vendor"] for po in pos.values()})

    already = {p["number"]: p for p in purchase_orders()}
    for number, po in pos.items():
        if number in already:
            # Already there. Fill in any lines a previous, interrupted run didn't finish.
            contract = already[number]
            have = {l["description"].split("|")[0].strip() for l in po_lines(contract["id"])}
            missing = [row for row in po["lines"] if row["item_code"] not in have]
            if not missing:
                print(f"  skip {number} (already in Procore)")
                continue
            print(f"  {number} exists; adding {len(missing)} missing line(s)")
        else:
            contract = call("POST", "/rest/v1.0/purchase_order_contracts", {
                "project_id": int(PROJECT),
                "purchase_order_contract": {
                    "number": number,
                    "title": f"Materials - {po['vendor']}",
                    "vendor_id": vids[po["vendor"]],
                    "status": "Approved",
                    "executed": True,
                },
            })
            missing = po["lines"]
        for row in missing:
            qty, price = float(row["qty_ordered"]), float(row["unit_price"])
            call("POST", f"/rest/v1.0/purchase_order_contracts/{contract['id']}/line_items", {
                "project_id": int(PROJECT),
                "line_item": {
                    "description": f"{row['item_code']} | {row['description']}",
                    "quantity": f"{qty:g}",
                    "unit_cost": f"{price:.2f}",
                    "amount": f"{qty * price:.2f}",
                    "uom": "EA",
                },
            })
        print(f"  {'created' if len(missing) == len(po['lines']) and number not in already else 'completed'} "
              f"{number} ({po['vendor']}, {len(po['lines'])} lines)")
    print("Done.")


if __name__ == "__main__":
    main()
