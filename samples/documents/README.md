# Sample documents for the demo

All documents are **fictional** and watermarked **SPECIMEN, FOR TESTING ONLY**. Names, numbers and addresses are made up and don't copy any real government design. Regenerate them with `cd backend && uv run python scripts/make_sample_docs.py`.

The residents match the demo units already seeded in the app.

## ✅ Correct documents (should show "Verified by AI")

| Demo | Society · unit | Tell the assistant | Upload |
|---|---|---|---|
| Owner move-in (auto-approved) | Green Valley · A-101 | "I'm Asha Rao, I own A-101, moving in Saturday 24 Oct afternoon, 3 of us, phone 9876543210" | `asha_id_proof.png` → Government ID · `asha_sale_deed.png` → Sale deed |
| Tenant move-in | Green Valley · B-302 | "I'm Karan Shah renting B-302 with my wife, phone 9812345678, moving Saturday 24 Oct morning" | `karan_id_proof.png` · `karan_rental_agreement.png` · `karan_police_verification.png` · `karan_owner_noc.png` |
| Tenant move-out | Green Valley · A-201 | "I'm Rahul Mehta, renting A-201, moving out Saturday 31 Oct afternoon, phone 9000022222" | `rahul_id_proof.png` · `rahul_owner_noc_moveout.png` → NOC from flat owner |
| Owner move-out with ₹8,200 dues (blocked) | Green Valley · A-202 | "I'm Priya Nair, I own A-202, moving out Sunday 1 Nov afternoon, phone 9000011111" | `priya_id_proof.png` |
| Tenant move-in | Sunrise Heights · 102 | "I'm Rohan Gupta renting 102, moving in Tuesday 27 Oct morning, phone 9045033200" | `rohan_id_proof.png` · `rohan_rental_agreement.png` |
| Tenant move-out with dues (warning only) | Sunrise Heights · 201 | "I'm Neha Kapoor renting 201, moving out Wednesday 28 Oct afternoon, phone 9000044444" | `neha_id_proof.png` · `neha_owner_noc_moveout.png` |
| Owner move-out | Sunrise Heights · 202 | "I'm Arjun Das, I own 202, moving out Friday 30 Oct evening, phone 9123456780" | `arjun_id_proof.png` |

Dates are examples: pick a date at least a week away. Green Valley allows Saturday and Sunday only; Sunrise Heights allows any day.

## ❌ Deliberately wrong documents (should show a problem)

| File | Upload it as | What the app should say |
|---|---|---|
| `BAD_karan_owner_noc_wrong_name.png` | Karan's NOC from flat owner | name on the document (Karan **Shaw**) doesn't match Karan **Shah** |
| `BAD_karan_police_verification_expired.png` | Karan's police verification | expired on 2026-08-31 |
| `BAD_grocery_receipt.png` | any document (e.g. Government ID) | the upload looks like a different document |
| `karan_rental_agreement.png` | Karan's **Government ID** | looks like a rental agreement, not a government ID |
| `asha_id_proof.png` | **Karan's** Government ID | name (Asha Rao) doesn't match Karan Shah |

## Best 2-minute demo
1. Karan's tenant move-in: upload three correct documents plus `BAD_karan_owner_noc_wrong_name.png`.
2. Ask the assistant **"Can I submit now?"**. It explains the NOC name problem.
3. Replace it with `karan_owner_noc.png`. Everything turns ✓, then say **"Yes, submit."**
