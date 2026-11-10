"""Generate fake sample data for the invoice checker demo.

Creates:
  data/purchase_orders.csv  - what the company ordered (from its own records)
  data/deliveries.csv       - what actually arrived at the job site
  invoices/*.pdf            - vendor invoices, each with a different layout

Some invoices contain deliberate problems so the checker has something to catch.
"""
import csv
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

DATA = Path("data")
INVOICES = Path("invoices")

# ---------------------------------------------------------------------------
# The company's records
# ---------------------------------------------------------------------------
PURCHASE_ORDERS = [
    # po_number, vendor, item_code, description, qty_ordered, unit_price
    ("PO-1001", "Metro Lighting Supply", "TRF-2X4", "2x4 LED flat panel 40W 4000K", 80, 72.00),
    ("PO-1001", "Metro Lighting Supply", "DRV-010", "0-10V dimmable LED driver 40W", 40, 54.50),
    ("PO-1002", "Empire Electrical Distributors", "CPL-075", "3/4in EMT compression coupling", 1500, 2.10),
    ("PO-1002", "Empire Electrical Distributors", "EMT-075", "3/4in EMT conduit 10ft", 80, 14.50),
    ("PO-1003", "Hudson Electrical Supply", "MC-122", "12/2 MC cable 250ft coil", 20, 118.00),
    ("PO-1003", "Hudson Electrical Supply", "BOX-4SQ", "4in square box", 200, 3.40),
    ("PO-1004", "Five Boro Sign Supply", "LED-M3", "LED sign module 3-LED, box of 50", 30, 64.00),
    ("PO-1004", "Five Boro Sign Supply", "PS-60W", "12V 60W sign power supply", 40, 38.50),
]

DELIVERIES = [
    # ticket, po_number, item_code, qty_received, date_received
    ("DT-5501", "PO-1001", "TRF-2X4", 80, "2026-10-14"),
    ("DT-5501", "PO-1001", "DRV-010", 40, "2026-10-14"),
    ("DT-5502", "PO-1002", "CPL-075", 1500, "2026-10-16"),
    ("DT-5502", "PO-1002", "EMT-075", 80, "2026-10-16"),
    ("DT-5503", "PO-1003", "MC-122", 16, "2026-10-20"),  # only 16 of 20 coils arrived
    ("DT-5503", "PO-1003", "BOX-4SQ", 200, "2026-10-20"),
    ("DT-5504", "PO-1004", "LED-M3", 30, "2026-10-21"),
    ("DT-5504", "PO-1004", "PS-60W", 40, "2026-10-21"),
]

# ---------------------------------------------------------------------------
# Vendor invoices (what the vendors claim)
# ---------------------------------------------------------------------------
INVOICE_SPECS = [
    {   # 1. Clean - everything matches
        "file": "metro_lighting_ML-88213.pdf",
        "style": "A",
        "vendor": "Metro Lighting Supply",
        "address": "1180 Metropolitan Ave, Brooklyn, NY 11237",
        "invoice_no": "ML-88213",
        "date": "10/15/2026",
        "po_label": "PO #",
        "po": "PO-1001",
        "lines": [
            ("TRF-2X4", "LED PANEL 2X4 40W 40K", 80, 72.00),
            ("DRV-010", "DRIVER 0-10V DIM 40W", 40, 54.50),
        ],
        "notes": "Terms: Net 30. Delivered to 450 E 52nd St jobsite.",
    },
    {   # 2. Price problem - EMT couplings billed at $2.35, PO says $2.10
        "file": "empire_electrical_INV-20417.pdf",
        "style": "B",
        "vendor": "Empire Electrical Distributors",
        "address": "77 Bruckner Blvd, Bronx, NY 10454",
        "invoice_no": "INV-20417",
        "date": "10/17/2026",
        "po_label": "Customer PO",
        "po": "PO-1002",
        "lines": [
            ("CPL-075", '3/4" EMT Compression Coupling', 1500, 2.35),
            ("EMT-075", "EMT 3/4\" x 10' Stick", 80, 14.50),
        ],
        "notes": "Price reflects current market adjustment. Remit within 30 days.",
    },
    {   # 3. Delivery problem - billed for 20 coils, only 16 delivered
        "file": "hudson_electrical_HE-7731.pdf",
        "style": "A",
        "vendor": "Hudson Electrical Supply",
        "address": "301 W 37th St, New York, NY 10018",
        "invoice_no": "HE-7731",
        "date": "10/21/2026",
        "po_label": "Your Order No.",
        "po": "PO-1003",
        "lines": [
            ("MC-122", "MC Cable 12/2 AL Armor 250' coil", 20, 118.00),
            ("BOX-4SQ", '4" Sq Box 2-1/8" deep', 200, 3.40),
        ],
        "notes": "Thank you for your business! Questions? Call the counter at ext. 4.",
    },
    {   # 4. Math problem - line items add up to $3,460.00 but invoice says $3,560.00
        "file": "five_boro_sign_FBF-3390.pdf",
        "style": "B",
        "vendor": "Five Boro Sign Supply",
        "address": "52-10 Grand Ave, Maspeth, NY 11378",
        "invoice_no": "FBF-3390",
        "date": "10/22/2026",
        "po_label": "Job / PO",
        "po": "PO-1004",
        "lines": [
            ("LED-M3", "3-LED Sign Module White (50/bx)", 30, 64.00),
            ("PS-60W", "Sign Power Supply 12VDC 60W", 40, 38.50),
        ],
        "stated_total": 3560.00,
        "notes": "Job: 450 E 52nd St. Signed delivery ticket on file.",
    },
    {   # 5. Duplicate - Metro Lighting re-sent invoice ML-88213 with a new layout
        "file": "metro_lighting_resent_ML-88213.pdf",
        "style": "B",
        "vendor": "Metro Lighting Supply",
        "address": "1180 Metropolitan Ave, Brooklyn, NY 11237",
        "invoice_no": "ML-88213",
        "date": "10/29/2026",
        "po_label": "Purchase Order",
        "po": "PO-1001",
        "lines": [
            ("TRF-2X4", "2x4 LED Flat Panel 40W", 80, 72.00),
            ("DRV-010", "LED Driver 0-10V Dimmable", 40, 54.50),
        ],
        "notes": "SECOND NOTICE - PLEASE REMIT. Disregard if already paid.",
    },
]


def money(x: float) -> str:
    return f"${x:,.2f}"


def line_cell(pdf: FPDF, w: float, h: float, text: str, align: str = "L", border=0):
    pdf.cell(w, h, text, border=border, align=align)


def build_style_a(spec: dict, subtotal: float, total: float) -> FPDF:
    """Vendor name on top, invoice details on the right, item code first."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(120, 10, spec["vendor"])
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 10, "INVOICE", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, spec["address"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 10)
    for label, value in [
        ("Invoice No.", spec["invoice_no"]),
        ("Invoice Date", spec["date"]),
        (spec["po_label"], spec["po"]),
        ("Bill To", "Northgate Facility Services LLC, 220 E 42nd St, New York, NY 10017"),
    ]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 6, label + ":")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    widths = [30, 80, 20, 30, 30]
    pdf.set_font("Helvetica", "B", 10)
    for w, head in zip(widths, ["Item", "Description", "Qty", "Unit Price", "Amount"]):
        line_cell(pdf, w, 8, head, "C", border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    for code, desc, qty, price in spec["lines"]:
        line_cell(pdf, widths[0], 8, code, border=1)
        line_cell(pdf, widths[1], 8, desc, border=1)
        line_cell(pdf, widths[2], 8, str(qty), "R", border=1)
        line_cell(pdf, widths[3], 8, money(price), "R", border=1)
        line_cell(pdf, widths[4], 8, money(qty * price), "R", border=1)
        pdf.ln()
    pdf.ln(4)

    for label, value in [("Subtotal", subtotal), ("Sales Tax (exempt)", 0.0), ("TOTAL DUE", total)]:
        pdf.set_font("Helvetica", "B" if label == "TOTAL DUE" else "", 10)
        pdf.cell(160, 7, label, align="R")
        pdf.cell(30, 7, money(value), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, spec["notes"])
    return pdf


def build_style_b(spec: dict, subtotal: float, total: float) -> FPDF:
    """Bill-to block first, quantity column first, different labels."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, spec["vendor"].upper(), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, spec["address"], align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(95, 6, "SOLD TO")
    pdf.cell(95, 6, "BILLING DETAILS", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    left = ["Northgate Facility Services LLC", "220 E 42nd St", "New York, NY 10017"]
    right = [
        f"Inv #: {spec['invoice_no']}",
        f"Dated: {spec['date']}",
        f"{spec['po_label']}: {spec['po']}",
    ]
    for l, r in zip(left, right):
        pdf.cell(95, 6, l)
        pdf.cell(95, 6, r, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    widths = [18, 32, 80, 30, 30]
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Helvetica", "B", 10)
    for w, head in zip(widths, ["QTY", "SKU", "DESCRIPTION", "EACH", "EXT"]):
        pdf.cell(w, 8, head, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 10)
    for code, desc, qty, price in spec["lines"]:
        line_cell(pdf, widths[0], 8, str(qty), "C")
        line_cell(pdf, widths[1], 8, code)
        line_cell(pdf, widths[2], 8, desc)
        line_cell(pdf, widths[3], 8, f"{price:,.2f}", "R")
        line_cell(pdf, widths[4], 8, f"{qty * price:,.2f}", "R")
        pdf.ln()
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(160, 7, "Merchandise", align="R")
    pdf.cell(30, 7, f"{subtotal:,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(160, 7, "Tax", align="R")
    pdf.cell(30, 7, "0.00", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(160, 8, "AMOUNT DUE", align="R")
    pdf.cell(30, 8, money(total), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, spec["notes"])
    return pdf


def write_csv(path: Path, header: list[str], rows: list[tuple]):
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    DATA.mkdir(exist_ok=True)
    INVOICES.mkdir(exist_ok=True)

    write_csv(
        DATA / "purchase_orders.csv",
        ["po_number", "vendor", "item_code", "description", "qty_ordered", "unit_price"],
        PURCHASE_ORDERS,
    )
    write_csv(
        DATA / "deliveries.csv",
        ["ticket", "po_number", "item_code", "qty_received", "date_received"],
        DELIVERIES,
    )

    for spec in INVOICE_SPECS:
        line_sum = sum(qty * price for _, _, qty, price in spec["lines"])
        # A planted math error prints a total that doesn't match the lines.
        total = spec.get("stated_total", line_sum)
        subtotal = total
        build = build_style_a if spec["style"] == "A" else build_style_b
        build(spec, subtotal, total).output(str(INVOICES / spec["file"]))
        print(f"  wrote invoices/{spec['file']}")

    print("Wrote data/purchase_orders.csv and data/deliveries.csv")


if __name__ == "__main__":
    main()
