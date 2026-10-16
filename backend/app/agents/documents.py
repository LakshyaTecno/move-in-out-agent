"""Document reader: a multimodal LLM looks at an uploaded file and reports
facts only (is it a document, which kind, whose names, expiry date). It does
not decide anything; app.core.doc_checks judges the facts against the request.

The file is sent to the model and then discarded; only the extracted facts
are stored."""

import base64
import os
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import LLMUnavailable, get_models

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "application/pdf"}
MAX_BYTES = 5 * 1024 * 1024


class DocumentReading(BaseModel):
    is_readable_document: bool = Field(
        description="False if the file is blank, too blurry to read, or not an official document "
        "at all (for example a receipt, a selfie, or a screenshot of a chat)."
    )
    detected_type: str = Field(description="Exactly one of the document type keys given, or 'other'.")
    names: list[str] = Field(description="Every person's full name exactly as written on the document.")
    valid_until: date | None = Field(description="Expiry or 'valid until' date if the document states one, else null.")
    notes: str = Field(description="One short sentence: anything that looks altered, inconsistent or suspicious. Empty if nothing.")


SYSTEM = """You read residential-society documents and report exactly what is written. Do not guess:
if something isn't on the document, leave it empty or null.
Document type keys (pick one, or 'other' if none fit):
{catalog}
{specimen_note}"""

SPECIMEN_NOTE = (
    "This environment uses test documents watermarked 'SPECIMEN' or marked '(SAMPLE)'. "
    "Read them like real documents and do not treat the watermark as a problem."
)


def read_document(content: bytes, mime_type: str, catalog: dict[str, str]) -> DocumentReading:
    """Raises LLMUnavailable if no model could read it; the caller then stores
    the document as unchecked so a human reviews it."""
    catalog_text = "\n".join(f"- {key}: {label}" for key, label in catalog.items())
    accept_specimens = os.getenv("DOC_CHECK_ACCEPT_SPECIMENS", "true").lower() == "true"
    messages = [
        SystemMessage(SYSTEM.format(catalog=catalog_text, specimen_note=SPECIMEN_NOTE if accept_specimens else "")),
        HumanMessage(content=[
            {"type": "text", "text": "Read this document."},
            {"type": "file" if mime_type == "application/pdf" else "image",
             "base64": base64.b64encode(content).decode(), "mime_type": mime_type},
        ]),
    ]
    try:
        primary, *fallbacks = [m.with_structured_output(DocumentReading) for m in get_models("document")]
        return primary.with_fallbacks(fallbacks).invoke(messages)
    except LLMUnavailable:
        raise
    except Exception as exc:
        raise LLMUnavailable(f"document could not be read by any model: {exc}") from exc
