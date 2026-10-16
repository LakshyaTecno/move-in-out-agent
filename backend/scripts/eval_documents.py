"""Mini eval: run the REAL document reader (Gemini) on the sample documents and
compare the final verdict with what we expect. Run from backend/:
    uv run python scripts/eval_documents.py
"""

import time
from pathlib import Path

import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from app.agents.documents import read_document  # noqa: E402
from app.core.community import get_community  # noqa: E402
from app.core.doc_checks import verdict  # noqa: E402
from app.core.models import Document, DocumentCheck  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "samples" / "documents"
CATALOG = get_community("green-valley").doc_catalog

# (file, uploaded as, resident name, expected verdict, expected expiry or None)
CASES = [
    ("asha_id_proof.png", "id_proof", "Asha Rao", "verified", "2034-12-31"),
    ("asha_sale_deed.png", "sale_deed", "Asha Rao", "verified", None),
    ("karan_id_proof.png", "id_proof", "Karan Shah", "verified", "2033-06-30"),
    ("karan_rental_agreement.png", "rental_agreement", "Karan Shah", "verified", "2027-08-31"),
    ("karan_police_verification.png", "police_verification", "Karan Shah", "verified", "2027-10-04"),
    ("karan_owner_noc.png", "owner_noc", "Karan Shah", "verified", None),
    ("BAD_karan_owner_noc_wrong_name.png", "owner_noc", "Karan Shah", "problem", None),
    ("BAD_karan_police_verification_expired.png", "police_verification", "Karan Shah", "verified", "2026-08-31"),
    ("BAD_grocery_receipt.png", "id_proof", "Karan Shah", "problem", None),
    ("karan_rental_agreement.png", "id_proof", "Karan Shah", "problem", "2027-08-31"),  # right file, wrong slot
]

passed = 0
for file, as_type, resident, expected, expected_expiry in CASES:
    t = time.time()
    r = read_document((SAMPLES / file).read_bytes(), "image/png", CATALOG)
    check = DocumentCheck(readable=r.is_readable_document,
                          detected_type=r.detected_type if r.detected_type in CATALOG else "other",
                          names_found=r.names, ai_notes=r.notes or None)
    got, message = verdict(Document(doc_type=as_type, file_name=file, check=check), resident, CATALOG)
    expiry = r.valid_until.isoformat() if r.valid_until else None
    ok = got == expected and expiry == expected_expiry
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'} {time.time()-t:4.1f}s  {file:44s} as {as_type:19s} → {got:9s} "
          f"expiry={expiry}  | {message}")
    time.sleep(4)  # stay under the free-tier rate limit

print(f"\n{passed}/{len(CASES)} cases correct")
print("Note: the expired police verification is 'verified' here (right person, right type); "
      "the separate document_validity rule fails it against the move date.")
