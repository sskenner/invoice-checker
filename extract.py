"step 3: have claude read each invoice PDF and pull out structured data."
import base64
import json
from pathlib import Path

import anthropic
from pydantic import BaseModel

INVOICES = Path("invoices")
EXTRACTED = Path("extracted")

# The exact shape we want back. claude's answer is forced to match this.
class LineItem(BaseModel):
    item_code: str
    description: str
    quantity: float
    unit_price: float
    line_total: float

class Invoice(BaseModel):
    vendor_name: str
    invoice_number: str
    invoice_date: str
    po_number: str | None
    line_items: list[LineItem]
    subtotal: float
    tax: float
    total_due: float
    notes: str | None

INSTRUCTIONS = """ Extract the data from this vendor invoice.

Copy every value exactly as printed, even if it looks wrong. Do not fix math, \
recalculate totals, or fill in anything that isn't there. A separate system \
checks the invoice afterward, so it needs to see what the vendor actually wrote.

- po_number: the buyer's purchase order number, whatever the vendor calls it \
("PO #", "Customer PO", "Your Order No.", etc.). Use null if there isn't one.
- invoice_date: convert to YYYY-MM-DD.
- line_total: the amount printed on that line, not your own calculation.
- notes: any remarks or messages printed on the invoice, or null.
"""

client = anthropic.Anthropic()

def extract_invoice(pdf_path: Path) -> Invoice | None:
    pdf_data = base64.standard_b64encode(pdf_path.read_bytes()).decode("utf-8")

    response = client.beta.messages.parse(
        model="claude-opus-5-5",
        max_tokens=16000,
        output_config={"effort": "medium"},
        # If Claude ever declines a request, retry it on a backup model automatically.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_data},
                },
                {"type": "text", "text": INSTRUCTIONS},
            ],
        }],
        output_format=Invoice,
    )

    if response.stop_reason != "end_turn":
        print(f"  !! {pdf_path.name}: stopped early ({response.stop_reason}), skipping")
        return None
    return response.parsed_output

def main():
    EXTRACTED.mkdir(exist_ok=True)

    for pdf_path in sorted(INVOICES.glob("*.pdf")):
        print(f"Reading {pdf_path.name} ...")
        invoice = extract_invoice(pdf_path)
        if invoice is None:
            continue

        out_path = EXTRACTED / (pdf_path.stem + ".json")
        out_path.write_text(json.dumps(invoice.model_dump(), indent=2))

        print(f"  {invoice.vendor_name} | invoice {invoice.invoice_number} | "
              f"PO {invoice.po_number} | {len(invoice.line_items)} lines | "
              f"total ${invoice.total_due:,.2f}")

    print(f"\nSaved results to {EXTRACTED}/")

if __name__ == "__main__":
    main()