"""Adapters for the three candidate PDF text extractors.

Each adapter takes a PDF path and returns one string per page (empty string
for pages the library returns None for). Adapters let library exceptions
propagate; the harness records them per file and continues.

Standing privacy rule: extracted text must never be logged from here or
anywhere else.
"""

from collections.abc import Callable
from pathlib import Path

import pdfplumber
import pymupdf
from pypdf import PdfReader

Extractor = Callable[[Path], list[str]]


def extract_with_pymupdf(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


def extract_with_pdfplumber(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def extract_with_pypdf(path: Path) -> list[str]:
    reader = PdfReader(path)
    return [page.extract_text() or "" for page in reader.pages]


EXTRACTORS: dict[str, Extractor] = {
    "pymupdf": extract_with_pymupdf,
    "pdfplumber": extract_with_pdfplumber,
    "pypdf": extract_with_pypdf,
}
