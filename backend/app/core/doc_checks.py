"""Judge what the AI read from an uploaded document. Pure code, no AI: the
model only reports facts (type, names, expiry); these functions decide whether
those facts are acceptable for this request."""

import re
from datetime import date
from enum import StrEnum

from app.core.models import Document

TITLES = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "kumari"}


class Verdict(StrEnum):
    VERIFIED = "verified"
    PROBLEM = "problem"
    UNVERIFIED = "unverified"  # never AI-checked, or the AI was unavailable
    WAITING = "waiting"  # can't compare yet (resident name not given)


def _tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z]+", name.casefold())
    return [w for w in words if w not in TITLES]


def names_match(a: str, b: str) -> bool:
    """Same person? Exact match, or same surname with a matching first initial,
    so "K. Shah" matches "Karan Shah" but "Karan Shaw" does not."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    return ta[-1] == tb[-1] and ta[0][0] == tb[0][0]


def verdict(doc: Document, resident_name: str | None, catalog: dict[str, str],
            expires_before: date | None = None) -> tuple[Verdict, str]:
    """expires_before: also report expiry on this document's own verdict (used
    for the per-document view). The policy engine leaves it None because the
    document_validity rule already owns expiry."""
    label = catalog.get(doc.doc_type, doc.doc_type)
    if expires_before and doc.valid_until and doc.valid_until < expires_before:
        return Verdict.PROBLEM, f"{label}: expired on {doc.valid_until}"
    check = doc.check
    if check is None or check.readable is None:
        return Verdict.UNVERIFIED, f"{label}: not verified by AI, check it manually"
    if not check.readable:
        return Verdict.PROBLEM, f"{label}: the upload isn't a readable document"
    if check.detected_type != doc.doc_type:
        looks_like = catalog.get(check.detected_type or "", "a different document")
        return Verdict.PROBLEM, f"{label}: the upload looks like {looks_like}, not a {label.lower()}"
    if not resident_name:
        return Verdict.WAITING, f"{label}: will be matched once the resident's name is given"
    if not any(names_match(n, resident_name) for n in check.names_found):
        found = ", ".join(check.names_found) or "no name"
        return Verdict.PROBLEM, f"{label}: name on the document ({found}) doesn't match {resident_name}"
    return Verdict.VERIFIED, f"{label}: verified"
