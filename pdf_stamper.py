"""
pdf_stamper.py
==============
Applies a stamp image onto PDF pages using PyMuPDF (fitz).
"""

import os
import uuid
import datetime
import fitz  # PyMuPDF
from config import Config


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _resolve_pages(page_spec: str, total_pages: int) -> list[int]:
    """
    Convert a page specification string to a list of 0-based page indices.

    Accepted values:
      - "all"          → every page
      - "first"        → page 0 only
      - "last"         → last page only
      - "1,3,5"        → explicit 1-based page numbers
      - "1-3"          → page range (1-based, inclusive)
    """
    spec = str(page_spec).strip().lower()
    if spec == "all":
        return list(range(total_pages))
    if spec == "first":
        return [0]
    if spec == "last":
        return [total_pages - 1]

    indices = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                a, b = int(a.strip()), int(b.strip())
                for p in range(a, b + 1):
                    if 1 <= p <= total_pages:
                        indices.add(p - 1)
            except ValueError:
                pass
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    indices.add(p - 1)
            except ValueError:
                pass
    return sorted(indices) if indices else [0]


def _stamp_position(placement: str, page_rect: fitz.Rect,
                    stamp_w: float, stamp_h: float,
                    custom_x: float = None, custom_y: float = None,
                    margin: float = 20):
    """Return the (x, y) top-left corner for the stamp on a page (PDF points)."""
    pw, ph = page_rect.width, page_rect.height

    positions = {
        "top-left":     (margin,              margin),
        "top-right":    (pw - stamp_w - margin, margin),
        "bottom-left":  (margin,              ph - stamp_h - margin),
        "bottom-right": (pw - stamp_w - margin, ph - stamp_h - margin),
        "center":       ((pw - stamp_w) / 2,  (ph - stamp_h) / 2),
    }

    if placement == "custom" and custom_x is not None and custom_y is not None:
        return float(custom_x), float(custom_y)

    return positions.get(placement, positions["bottom-right"])


def stamp_pdf(input_pdf_path: str,
              stamp_image_path: str,
              placement: str = "bottom-right",
              pages: str = "all",
              opacity: float = 0.85,
              stamp_width_pt: float = 120,
              custom_x: float = None,
              custom_y: float = None) -> str:
    """
    Stamp a PDF with the given image and return the path to the output PDF.

    Parameters
    ----------
    input_pdf_path : str  – absolute path to the source PDF
    stamp_image_path : str – absolute path to the stamp PNG
    placement : str       – "top-left", "top-right", "bottom-left",
                            "bottom-right", "center", or "custom"
    pages : str           – "all", "first", "last", "1,3", "2-4", …
    opacity : float       – 0.0 (transparent) to 1.0 (opaque)
    stamp_width_pt : float – desired stamp width in PDF points
    custom_x, custom_y   – top-left corner for custom placement

    Returns
    -------
    str – relative path (from static/) to the output PDF
    """
    _ensure_dir(Config.UPLOAD_FOLDER)

    out_dir  = Config.UPLOAD_FOLDER
    ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid      = uuid.uuid4().hex[:8]
    out_name = f"stamped_{ts}_{uid}.pdf"
    out_path = os.path.join(out_dir, out_name)

    doc = fitz.open(input_pdf_path)
    total_pages = len(doc)
    page_indices = _resolve_pages(pages, total_pages)

    # Load stamp image into a pixmap
    stamp_pix = fitz.Pixmap(stamp_image_path)

    # Compute stamp dimensions maintaining aspect ratio
    ratio      = stamp_pix.height / stamp_pix.width
    stamp_w_pt = stamp_width_pt
    stamp_h_pt = stamp_width_pt * ratio

    for idx in page_indices:
        page = doc[idx]
        x, y = _stamp_position(
            placement, page.rect, stamp_w_pt, stamp_h_pt,
            custom_x=custom_x, custom_y=custom_y
        )
        rect = fitz.Rect(x, y, x + stamp_w_pt, y + stamp_h_pt)
        page.insert_image(rect, pixmap=stamp_pix, overlay=True,
                          keep_proportion=True, rotate=0)

    doc.save(out_path, garbage=4, deflate=True)
    doc.close()

    return os.path.join("uploads", out_name).replace("\\", "/")


def get_pdf_info(pdf_path: str) -> dict:
    """Return basic metadata about a PDF file."""
    try:
        doc  = fitz.open(pdf_path)
        meta = doc.metadata
        info = {
            "pages":     len(doc),
            "title":     meta.get("title", ""),
            "author":    meta.get("author", ""),
            "width_pt":  doc[0].rect.width  if len(doc) > 0 else 0,
            "height_pt": doc[0].rect.height if len(doc) > 0 else 0,
        }
        doc.close()
        return info
    except Exception as e:
        return {"error": str(e)}


def generate_pdf_preview(pdf_path: str, page: int = 0, dpi: int = 96) -> str:
    """
    Render a PDF page to a PNG preview and return its relative URL path.
    Returns relative path from static/.
    """
    _ensure_dir(Config.GENERATED_FOLDER)
    try:
        doc  = fitz.open(pdf_path)
        pg   = doc[min(page, len(doc) - 1)]
        mat  = fitz.Matrix(dpi / 72, dpi / 72)
        pix  = pg.get_pixmap(matrix=mat, alpha=False)
        doc.close()

        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        uid      = uuid.uuid4().hex[:8]
        fname    = f"preview_{ts}_{uid}.png"
        out_path = os.path.join(Config.GENERATED_FOLDER, fname)
        pix.save(out_path)
        return os.path.join("generated", fname).replace("\\", "/")
    except Exception as e:
        raise RuntimeError(f"Could not render PDF preview: {e}")
