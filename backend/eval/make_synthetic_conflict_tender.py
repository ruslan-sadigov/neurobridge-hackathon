"""Generate a small FICTIONAL two-document tender package with planted contradictions and decoys.

  python -m eval.make_synthetic_conflict_tender      # writes fixtures/tenders/SYN_*.pdf

Planted conflicts (the two documents disagree):   submission deadline, minimum turnover, tender validity.
Decoys (must NOT be flagged):                      performance guarantee for Lot 1 vs Lot 2 (different lots),
                                                   identical bid security (consistent), ISO 9001 vs ISO 27001
                                                   (two different certificates, both required).
Everything here is invented for testing; no real organisation or tender is represented.
"""
from pathlib import Path

import pymupdf

OUT = Path("fixtures/tenders")

DOCS = {
    "SYN_conflict_tender_1_invitation.pdf": (
        "Invitation to Tender (fictional)\nMinistry of Digital Services - Supply and Installation of Network Equipment\n"
        "Reference SYN-2027-001\n\n"
        "1. Tenders must be submitted no later than 15 March 2027 at 12:00 (local time).\n\n"
        "2. The bidder must demonstrate an average annual turnover of at least EUR 2,000,000 over the last three years.\n\n"
        "3. Tenders must remain valid for 90 days after the submission deadline.\n\n"
        "4. For Lot 1, the successful bidder must provide a performance guarantee of 5% of the contract value.\n\n"
        "5. A bid security of EUR 50,000 must be submitted with the tender.\n\n"
        "6. The bidder must hold a valid ISO 9001 certificate."),
    "SYN_conflict_tender_2_datasheet.pdf": (
        "Tender Data Sheet (fictional)\nMinistry of Digital Services - Supply and Installation of Network Equipment\n"
        "Reference SYN-2027-001\n\n"
        "1. The deadline for submission of tenders is 22 March 2027 at 12:00 (local time).\n\n"
        "2. A minimum average annual turnover of EUR 3,000,000 over the last three years is required.\n\n"
        "3. Bids shall be valid for 120 days from the date of the submission deadline.\n\n"
        "4. For Lot 2, the successful bidder must provide a performance guarantee of 10% of the contract value.\n\n"
        "5. A bid security of EUR 50,000 is required.\n\n"
        "6. The bidder must hold a valid ISO 27001 certificate."),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in DOCS.items():
        doc = pymupdf.open()
        page = doc.new_page()
        rc = page.insert_textbox(pymupdf.Rect(60, 60, 535, 780), text, fontsize=11, fontname="helv")
        assert rc >= 0, "text did not fit on the page"
        doc.save(OUT / name)
        print("wrote", OUT / name)
