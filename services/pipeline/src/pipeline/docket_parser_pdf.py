"""PDF-opening wrapper for the docket parser (Task 17.2).

Holds ``parse_docket``, split out from ``docket_parser`` so that module's path
stays pdfplumber-free (acceptance criterion 1). This is a faithful port of
Capstone's ``parse_docket``: the same plain ``pdfplumber.open`` loop, the same
per-page ``extract_text() or ""`` fallback, the same ParseError on read
failure. It is deliberately NOT routed through ``pipeline.extraction``; that
16.2 stage carries threshold/status logic Capstone never had, and fidelity
means porting Capstone's loop even though 17.1 proved the extraction seams
equivalent.

Two changes from Capstone, both plan-approved and behavior-neutral:
- ``docket_number`` is an explicit parameter, never derived from the filename
  stem (decision 4; filename provenance is the import stage's business).
- ``salt`` is a required keyword-only parameter threaded to parse_docket_text
  (the 16.1 identity surface reads no environment).
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from pipeline.docket_parser import parse_docket_text
from pipeline.helpers import ParseError


def parse_docket(
    pdf_path: Path, docket_number: str, *, salt: str
) -> tuple[dict, list[str], list[dict[str, object]]]:
    """Parse one docket sheet PDF.

    Returns (record, sentinels, warnings): record matches the JSON contract;
    sentinels are the transient identifying strings (printed name, name parts,
    DOB text) for the privacy check; warnings are the structural-only parse-time
    warnings (18.2). Raises ParseError when the sheet cannot be read; error
    messages never quote docket text.
    """
    # Extract text and split by line
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text is None:
                    text = ""
                pages_text.append(text)
    except Exception as exc:
        raise ParseError(f"Failed to open/read PDF file: {type(exc).__name__}") from exc

    return parse_docket_text(docket_number, pages_text, salt=salt)
