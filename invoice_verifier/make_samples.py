import pymupdf


def make_invoice(filename, number, date, items, taxable, tax, grand):
    doc = pymupdf.open()
    page = doc.new_page()
    lines = [
        "TAX INVOICE",
        f"Invoice No: {number}",
        f"Invoice Date: {date}",
        "Dealer: Sri Murugan Dairy Traders",
        "Dealer GSTIN: 33AAAAA0000A1Z5",
        "Buyer: Annapoorna Stores",
        "Buyer GSTIN: 33BBBBB1111B1Z6",
        "",
        "Items (description | HSN | qty | rate | amount)",
    ]
    for i, (desc, hsn, qty, rate, amt) in enumerate(items, start=1):
        lines.append(f"{i}. {desc} | {hsn} | {qty} | {rate:.2f} | {amt:.2f}")
    lines += [
        "",
        f"Taxable Total: {taxable:.2f}",
        f"GST Total: {tax:.2f}",
        f"Grand Total: {grand:.2f}",
    ]
    y = 60
    for line in lines:
        page.insert_text((50, y), line, fontsize=11)
        y += 20
    doc.save(f"data/samples/{filename}")
    doc.close()
    print("created", filename)


good_items = [("Milk Pack 500ml", "04012000", 10, 50.00, 500.00),
              ("Curd Cup 200g", "04031000", 20, 25.00, 500.00)]

# 1. Everything correct -> should be Verified
make_invoice("sample_good.pdf", "INV-1001", "2026-11-10", good_items, 1000.00, 50.00, 1050.00)

# 2. Grand total is wrong -> should be Flagged or Review
make_invoice("sample_bad_math.pdf", "INV-1002", "2026-11-11", good_items, 1000.00, 50.00, 1500.00)

# 3. Date in the future -> should be Flagged
make_invoice("sample_future.pdf", "INV-1003", "2027-05-01", good_items, 1000.00, 50.00, 1050.00)