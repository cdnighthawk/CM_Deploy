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


def test_extract_keeps_forwarded_from_address():
    from app.ap._parse import extract_forwarded_origin, looks_like_forward

    subject = "FW: Invoice 15318 from Accurate Door Solutions, Inc."
    body = (
        "Charles Dossett | PRESIDENT<br>"
        "From: Harmony King &lt;harmony@ddh.net&gt;<br>"
        "Sent: Friday, June 5, 2026 7:35 AM<br>"
        "To: Pamela Ortega &lt;portega@gousis.com&gt;<br>"
        "Subject: Invoice 15318 from Accurate Door Solutions, Inc.<br>"
        "Amount Due: $247,711.00"
    )
    parsed = extract_invoice_fields(subject, body)
    assert parsed["invoice_number"] == "15318"
    assert parsed["amount"] == "247711.00"
    origin = extract_forwarded_origin(subject, body)
    assert origin["email"] == "harmony@ddh.net"
    assert origin["name"] == "Harmony King"
    assert origin["company"] == "Accurate Door Solutions, Inc."
    assert origin["is_forward"] is True
    assert looks_like_forward(subject, body) is True

    outlook_html = (
        '<b><span style="font-size:11.0pt">From:</span></b>'
        '<span style="font-size:11.0pt"> Harmony King &lt;harmony@ddh.net&gt; <br>'
        "<b>Sent:</b> Friday, June 5, 2026 7:35 AM</span>"
    )
    html_origin = extract_forwarded_origin(subject, outlook_html, skip_domains={"gousis.com"})
    assert html_origin["email"] == "harmony@ddh.net"
    assert html_origin["name"] == "Harmony King"


def test_extract_gmail_and_outlook_mailto_forwards():
    from app.ap._parse import extract_forwarded_origin

    gmail = (
        "---------- Forwarded message ---------<br>"
        "From: Harmony King &lt;harmony@ddh.net&gt;<br>"
        "Date: Fri, Jun 5, 2026 at 7:35 AM<br>"
        "Subject: Invoice 15318<br>"
    )
    origin = extract_forwarded_origin("Invoice 15318", gmail, skip_domains={"gousis.com"})
    assert origin["email"] == "harmony@ddh.net"
    assert origin["is_forward"] is True

    outlook = "From: Harmony King [mailto:harmony@ddh.net]\nSent: Friday, June 5, 2026 7:35 AM\n"
    mailto = extract_forwarded_origin("Invoice", outlook, skip_domains={"gousis.com"})
    assert mailto["email"] == "harmony@ddh.net"
    assert mailto["name"] == "Harmony King"


def test_extract_skips_internal_forwarded_from():
    from app.ap._parse import extract_forwarded_origin

    body = (
        "From: Pamela Ortega &lt;portega@gousis.com&gt;\n"
        "From: Harmony King &lt;harmony@ddh.net&gt;\n"
    )
    origin = extract_forwarded_origin("FW: Invoice", body, skip_domains={"gousis.com"})
    assert origin["email"] == "harmony@ddh.net"
