"""
pdfedit – place a graphic onto a page of an existing PDF.

Coordinates are in millimeters, origin at top-left of the page.
Usage:
    python main.py [--pdffile FILE] [--gfxfile FILE] [--posX MM] [--posY MM]
                   [--width MM] [--height MM] [--page N] [--insertmode MODE]
If any argument is omitted the program enters interactive mode for that value.

Insert modes:
  normal  – overlay the image directly (default)
  darken  – only copy a pixel from t2026-06-15 Jähricher_Datenabgleich Luise Hartlieb.pdfhe graphic if it is darker than the
            corresponding PDF pixel (useful for placing dark signatures on
            white/light backgrounds without a white box around them)
"""

import argparse
import sys
from pathlib import Path

MM_TO_PT = 72.0 / 25.4  # 1 mm in PDF points

INPUT_PDF_DIR = Path(__file__).parent / "input-pdf"
INPUT_GFX_DIR = Path(__file__).parent / "input-gfx"
OUTPUT_PDF_DIR = Path(__file__).parent / "output-pdf"


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------


def _pick_from_list(items: list[Path], label: str) -> Path:
    """Print a numbered list and return the user-selected Path."""
    if not items:
        print(
            f"Error: No {label} files found in the expected directory.", file=sys.stderr
        )
        sys.exit(1)
    print(f"\nAvailable {label} files:")
    for i, p in enumerate(items, 1):
        print(f"  {i}. {p.name}")
    while True:
        raw = input(f"Select {label} [1-{len(items)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        print(f"  Please enter a number between 1 and {len(items)}.")


def _ask_float(prompt: str, *, allow_blank: bool = False) -> float | None:
    """Prompt for a float, re-prompt on invalid input. Returns None if blank is allowed and entered."""
    while True:
        raw = input(prompt).strip()
        if allow_blank and raw == "":
            return None
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a valid number.")


def _ask_int(prompt: str, *, min_val: int = 1) -> int:
    """Prompt for an integer ≥ min_val."""
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if val >= min_val:
                return val
            print(f"  Please enter a number ≥ {min_val}.")
        except ValueError:
            print("  Please enter a valid integer.")


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def resolve_pdffile(value: str | None) -> Path:
    if value:
        p = Path(value)
        if not p.is_absolute():
            p = INPUT_PDF_DIR / p
        if not p.exists():
            print(f"Error: PDF file not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p
    pdfs = sorted(INPUT_PDF_DIR.glob("*.pdf"))
    return _pick_from_list(pdfs, "PDF")


def resolve_gfxfile(value: str | None) -> Path:
    if value:
        p = Path(value)
        if not p.is_absolute():
            p = INPUT_GFX_DIR / p
        if not p.exists():
            print(f"Error: Graphics file not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p
    gfx = sorted(
        f for ext in ("*.jpg", "*.jpeg", "*.png") for f in INPUT_GFX_DIR.glob(ext)
    )
    return _pick_from_list(gfx, "graphics (jpg/png)")


def resolve_page(value: int | None, max_page: int) -> int:
    if value is not None:
        if not (1 <= value <= max_page):
            print(
                f"Error: Page {value} is out of range (1–{max_page}).", file=sys.stderr
            )
            sys.exit(1)
        return value
    return _ask_int(f"Page number [1-{max_page}]: ", min_val=1)


# ---------------------------------------------------------------------------
# Scaling logic
# ---------------------------------------------------------------------------


def compute_dimensions(
    width_mm: float | None,
    height_mm: float | None,
    orig_w_pt: float,
    orig_h_pt: float,
) -> tuple[float, float]:
    """Return (width_pt, height_pt) after applying proportional scaling rules."""
    if width_mm is not None and height_mm is not None:
        return width_mm * MM_TO_PT, height_mm * MM_TO_PT
    if width_mm is not None:
        w_pt = width_mm * MM_TO_PT
        h_pt = w_pt * (orig_h_pt / orig_w_pt)
        return w_pt, h_pt
    if height_mm is not None:
        h_pt = height_mm * MM_TO_PT
        w_pt = h_pt * (orig_w_pt / orig_h_pt)
        return w_pt, h_pt
    # Neither given – use original image dimensions
    return orig_w_pt, orig_h_pt


# ---------------------------------------------------------------------------
# Core placement
# ---------------------------------------------------------------------------


def _darken_blend(pdf_path: Path, gfx_path: Path, rect, page, doc) -> None:
    """
    Render the target rect from the PDF page, blend with the gfx using the
    'darken' rule (result = min(pdf_pixel, gfx_pixel) per channel), then
    insert the composited image back into the same rect.
    """
    try:
        import fitz  # PyMuPDF
        from PIL import Image, ImageChops
        import io
    except ImportError as exc:
        print(
            f"Error: required package not installed ({exc}). Run: uv sync",
            file=sys.stderr,
        )
        sys.exit(1)

    # Render the PDF clip at the gfx's natural pixel width for best fidelity
    gfx_pil = Image.open(str(gfx_path)).convert("RGB")
    gfx_natural_w_px = gfx_pil.size[0]
    scale = gfx_natural_w_px / rect.width  # pixels per point
    mat = fitz.Matrix(scale, scale)
    clip_pixmap = page.get_pixmap(matrix=mat, clip=rect)
    pdf_pil = Image.open(io.BytesIO(clip_pixmap.tobytes("png"))).convert("RGB")

    # Resize gfx to exactly match the rendered PDF clip size
    gfx_resized = gfx_pil.resize(pdf_pil.size, Image.Resampling.LANCZOS)

    # Darken: keep the darker of the two pixels for every channel
    result = ImageChops.darker(pdf_pil, gfx_resized)

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue())


def place_image(
    pdf_path: Path,
    gfx_path: Path,
    pos_x_mm: float,
    pos_y_mm: float,
    width_mm: float | None,
    height_mm: float | None,
    page_number: int,  # 1-based
    mode: str = "normal",
) -> Path:
    """Open the PDF, insert the image, save to output-pdf/. Returns the output path."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    doc = fitz.open(str(pdf_path))
    page_idx = page_number - 1  # 0-based

    if page_idx >= len(doc):
        print(
            f"Error: Page {page_number} does not exist; the PDF has {len(doc)} page(s).",
            file=sys.stderr,
        )
        doc.close()
        sys.exit(1)

    page = doc[page_idx]

    # Determine original image dimensions by opening the graphic via PyMuPDF
    img_doc = fitz.open(str(gfx_path))
    img_page = img_doc[0]
    orig_w_pt: float = img_page.rect.width
    orig_h_pt: float = img_page.rect.height
    img_doc.close()

    width_pt, height_pt = compute_dimensions(width_mm, height_mm, orig_w_pt, orig_h_pt)

    # PyMuPDF Rect uses top-left origin (y increases downward) – no flip needed
    x0 = pos_x_mm * MM_TO_PT
    y0 = pos_y_mm * MM_TO_PT
    rect = fitz.Rect(x0, y0, x0 + width_pt, y0 + height_pt)

    if mode == "darken":
        _darken_blend(pdf_path, gfx_path, rect, page, doc)
    else:
        page.insert_image(rect, filename=str(gfx_path))

    OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_PDF_DIR / pdf_path.name
    doc.save(str(output_path))
    doc.close()

    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Place a graphic onto a page of an existing PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pdffile", help="PDF file (name inside input-pdf/ or full path)"
    )
    parser.add_argument(
        "--gfxfile", help="Image file (name inside input-gfx/ or full path)"
    )
    parser.add_argument("--posX", type=float, help="X position in mm (top-left origin)")
    parser.add_argument("--posY", type=float, help="Y position in mm (top-left origin)")
    parser.add_argument(
        "--width", type=float, help="Width in mm (omit to scale proportionally)"
    )
    parser.add_argument(
        "--height", type=float, help="Height in mm (omit to scale proportionally)"
    )
    parser.add_argument("--page", type=int, help="Page number (1-based, default: ask)")
    parser.add_argument(
        "--insertmode",
        choices=["normal", "darken"],
        default="normal",
        help="normal: overlay image directly (default); darken: only copy pixels darker than the PDF",
    )

    args = parser.parse_args()

    # Track whether any value was obtained interactively
    interactive = not all(
        [
            args.pdffile,
            args.gfxfile,
            args.posX is not None,
            args.posY is not None,
            args.page is not None,
            # width/height are intentionally optional, so they don't count
        ]
    )

    # Resolve files first so we know the page count before asking
    pdf_path = resolve_pdffile(args.pdffile)
    gfx_path = resolve_gfxfile(args.gfxfile)

    # We need the page count to validate / prompt for page number
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    with fitz.open(str(pdf_path)) as _doc:
        page_count = len(_doc)

    page_number = resolve_page(args.page, page_count)

    pos_x = (
        args.posX
        if args.posX is not None
        else _ask_float("posX (mm, top-left origin): ")
    )
    pos_y = (
        args.posY
        if args.posY is not None
        else _ask_float("posY (mm, top-left origin): ")
    )
    assert (
        pos_x is not None and pos_y is not None
    )  # allow_blank=False guarantees a value

    width = args.width
    height = args.height
    if width is None and height is None:
        print(
            "\nEnter width and/or height in mm. Leave both blank to use the original image size."
        )
        print("Enter only one to scale proportionally.")
        width = _ask_float("width  (mm, blank = auto): ", allow_blank=True)
        height = _ask_float("height (mm, blank = auto): ", allow_blank=True)
        if width is not None or height is not None:
            interactive = True

    output_path = place_image(
        pdf_path,
        gfx_path,
        pos_x,
        pos_y,
        width,
        height,
        page_number,
        mode=args.insertmode,
    )
    print(f"\nSaved: {output_path}")

    if interactive:
        parts = [f"python {Path(__file__).name}"]
        parts.append(f'--pdffile "{pdf_path.name}"')
        parts.append(f'--gfxfile "{gfx_path.name}"')
        parts.append(f"--posX {pos_x}")
        parts.append(f"--posY {pos_y}")
        if width is not None:
            parts.append(f"--width {width}")
        if height is not None:
            parts.append(f"--height {height}")
        parts.append(f"--page {page_number}")
        if args.insertmode != "normal":
            parts.append(f"--insertmode {args.insertmode}")
        print(f"\nEquivalent command:\n  {' '.join(parts)}")


if __name__ == "__main__":
    main()
