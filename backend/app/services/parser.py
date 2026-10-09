"""Page-aware PDF parsing with OCR fallback (FR-002/003). Every chunk keeps document_id + page_number."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..config import get_settings


@dataclass
class PageChunk:
    document_id: str
    page_number: int
    text: str
    extraction_method: str  # native | ocr | failed


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name.split("/")[-1].split("\\")[-1])[:120] or "upload.pdf"


def checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def parse_pdf(document_id: str, data: bytes) -> list[PageChunk]:
    import fitz  # PyMuPDF

    s = get_settings()
    chunks: list[PageChunk] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, 1):
            text = page.get_text("text").strip()
            method = "native"
            if len(text) < s.min_chars_per_page and s.ocr_enabled:
                ocr_text = _ocr_page(page)
                if ocr_text is not None:
                    text, method = ocr_text, "ocr"
                elif not text:
                    method = "failed"  # surfaced as incomplete coverage, never silently dropped
            chunks.append(PageChunk(document_id, i, text, method))
    return chunks


def _ocr_page(page) -> str | None:
    try:
        import io

        import pytesseract
        from PIL import Image

        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang=get_settings().ocr_langs).strip()
    except Exception:  # OCR not installed / failed
        return None


def coverage(chunks: list[PageChunk]) -> float:
    """Share of pages with usable text; warn the user if < 1.0 (spec section 13)."""
    return sum(1 for c in chunks if c.extraction_method != "failed" and c.text) / len(chunks) if chunks else 0.0
