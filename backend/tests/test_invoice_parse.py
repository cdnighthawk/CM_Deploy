from app.ap._parse import extract_invoice_fields


def test_extract_invoice_number_amount_po_and_job():
    subject = "Invoice INV-4412 for Job 24-018"
    body = "Please pay invoice INV-4412. PO #PO-9001. Amount due: $1,250.00"
    parsed = extract_invoice_fields(subject, body)
    assert parsed["invoice_number"] == "INV-4412"
    assert parsed["po_number"] == "PO-9001"
    assert parsed["amount"] == "1250.00"
    assert "24-018" in parsed["job_tokens"]


def test_extract_strips_html_and_picks_total():
    body = "<p>Line 1 $10.00</p><p>Total: $88.50</p>"
    parsed = extract_invoice_fields("Vendor bill", body)
    assert parsed["amount"] == "88.50"
