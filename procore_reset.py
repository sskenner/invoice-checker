"""Procore demo reset: delete the demo's purchase orders from the sandbox project.

Only POs whose numbers appear in data/purchase_orders.csv are touched; anything else
in the project is left alone. Vendors are kept (procore_seed.py reuses them).

    python procore_reset.py          asks you to type yes first
    python procore_reset.py --yes    no prompt (the teleprompter button confirms in the browser)

Run procore_seed.py afterwards to put the POs back.
"""
import csv
import sys
from pathlib import Path

from procore_api import PROJECT, call, purchase_orders

CSV = Path("data/purchase_orders.csv")


def main():
    with CSV.open() as f:
        demo_numbers = {row["po_number"] for row in csv.DictReader(f)}

    targets = sorted((p for p in purchase_orders() if p["number"] in demo_numbers),
                     key=lambda p: p["number"])
    if not targets:
        raise SystemExit("Nothing to delete.")

    for p in targets:
        print(f"  {p['number']}  {p['title']}")
    if "--yes" not in sys.argv:
        answer = input(f"\nDelete these {len(targets)} purchase order(s) from Procore project {PROJECT}? Type yes: ")
        if answer.strip().lower() != "yes":
            raise SystemExit("Cancelled. Nothing deleted.")

    for p in targets:
        # Procore won't delete an approved PO, so move it back to Draft first.
        if p.get("status") != "Draft":
            call("PATCH", f"/rest/v1.0/purchase_order_contracts/{p['id']}", {
                "project_id": int(PROJECT),
                "purchase_order_contract": {"status": "Draft", "executed": False},
            })
        call("DELETE", f"/rest/v1.0/purchase_order_contracts/{p['id']}?project_id={PROJECT}")
        print(f"  deleted {p['number']}")
    print("Run procore_seed.py to recreate them.")


if __name__ == "__main__":
    main()
