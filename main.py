"""PDFEdit CLI: stamp, merge, append, rotate, delete and replace pages in PDFs."""

import argparse
import os
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


def resolve_pdffile2(value: str | None) -> Path:
    if value:
        p = Path(value)
        if not p.is_absolute():
            p = INPUT_PDF_DIR / p
        if not p.exists():
            print(f"Error: Secondary PDF file not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p
    pdfs = sorted(INPUT_PDF_DIR.glob("*.pdf"))
    return _pick_from_list(pdfs, "secondary PDF")


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


def parse_page_ranges(expr: str, max_page: int) -> list[int]:
    """Parse page specs like '1, 2, 5-10' into sorted unique 1-based page numbers."""
    raw = expr.strip()
    if not raw:
        print("Error: --pages cannot be empty.", file=sys.stderr)
        sys.exit(1)

    pages: set[int] = set()
    for token in raw.split(","):
        part = token.strip()
        if not part:
            continue

        if "-" in part:
            start_raw, end_raw = part.split("-", 1)
            if not start_raw.strip().isdigit() or not end_raw.strip().isdigit():
                print(f"Error: Invalid range '{part}' in --pages.", file=sys.stderr)
                sys.exit(1)
            start = int(start_raw.strip())
            end = int(end_raw.strip())
            if start > end:
                print(
                    f"Error: Invalid range '{part}' (start must be <= end).",
                    file=sys.stderr,
                )
                sys.exit(1)
            for p in range(start, end + 1):
                pages.add(p)
        else:
            if not part.isdigit():
                print(f"Error: Invalid page '{part}' in --pages.", file=sys.stderr)
                sys.exit(1)
            pages.add(int(part))

    if not pages:
        print("Error: --pages did not contain any valid page.", file=sys.stderr)
        sys.exit(1)

    for p in pages:
        if not (1 <= p <= max_page):
            print(
                f"Error: Page {p} in --pages is out of range (1-{max_page}).",
                file=sys.stderr,
            )
            sys.exit(1)

    return sorted(pages)


def resolve_output_path(value: str | None, source_pdf_path: Path) -> Path:
    if value:
        p = Path(value)
        if not p.is_absolute():
            p = OUTPUT_PDF_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_PDF_DIR / source_pdf_path.name


def _read_env_value(key: str) -> str | None:
    """Read a key from environment, then from local .env file if needed."""
    env_val = os.getenv(key)
    if env_val:
        return env_val

    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return None

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k, v = stripped.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return None


def resolve_password(value: str | None) -> str:
    """Resolve password from arg or PDFEDIT_DEFAULT_PASSWORD in environment/.env."""
    if value:
        return value
    default_pw = _read_env_value("PDFEDIT_DEFAULT_PASSWORD")
    if default_pw:
        return default_pw
    print(
        "Error: No password provided. Use --password or set PDFEDIT_DEFAULT_PASSWORD in .env.",
        file=sys.stderr,
    )
    sys.exit(1)


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
    out_file: str | None = None,
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

    output_path = resolve_output_path(out_file, pdf_path)
    doc.save(str(output_path))
    doc.close()

    return output_path


# ---------------------------------------------------------------------------
# Operation boilerplate
# ---------------------------------------------------------------------------


def _not_implemented(operation: str) -> None:
    """Common placeholder until operation details are provided."""
    print(
        f"Error: operation '{operation}' is wired but not implemented yet.",
        file=sys.stderr,
    )
    print("Provide operation-specific instructions to implement this mode.")
    sys.exit(2)


def run_stamp(args: argparse.Namespace) -> None:
    """Execute the existing stamp operation."""
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
        out_file=args.outfile,
    )
    print(f"\nSaved: {output_path}")

    if interactive:
        parts = [f"python {Path(__file__).name}"]
        parts.append(f"--operation {args.operation}")
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
        if args.outfile:
            parts.append(f'--outfile "{args.outfile}"')
        print(f"\nEquivalent command:\n  {' '.join(parts)}")


def run_merge(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf1 = resolve_pdffile(args.pdffile)
    pdf2 = resolve_pdffile2(args.pdffile2)

    doc1 = fitz.open(str(pdf1))
    doc2 = fitz.open(str(pdf2))
    out = fitz.open()

    total1 = len(doc1)
    total2 = len(doc2)
    max_len = max(total1, total2)
    reverse_back = args.backsideorder == "reverse"

    for i in range(max_len):
        if i < total1:
            out.insert_pdf(doc1, from_page=i, to_page=i)
        idx2 = (total2 - 1 - i) if reverse_back else i
        if 0 <= idx2 < total2:
            out.insert_pdf(doc2, from_page=idx2, to_page=idx2)

    out_path = resolve_output_path(args.outfile, pdf1)
    out.save(str(out_path))
    doc1.close()
    doc2.close()
    out.close()
    print(f"\nSaved: {out_path}")


def run_append(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf1 = resolve_pdffile(args.pdffile)
    pdf2 = resolve_pdffile2(args.pdffile2)

    out = fitz.open(str(pdf1))
    src = fitz.open(str(pdf2))
    out.insert_pdf(src)

    out_path = resolve_output_path(args.outfile, pdf1)
    out.save(str(out_path))
    src.close()
    out.close()
    print(f"\nSaved: {out_path}")


def run_rotate(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf = resolve_pdffile(args.pdffile)
    doc = fitz.open(str(pdf))

    if args.pages:
        page_numbers = parse_page_ranges(args.pages, len(doc))
    else:
        page_numbers = list(range(1, len(doc) + 1))

    delta = 90 if args.direction == "cw" else -90
    for p in page_numbers:
        page = doc[p - 1]
        page.set_rotation((page.rotation + delta) % 360)

    out_path = resolve_output_path(args.outfile, pdf)
    doc.save(str(out_path))
    doc.close()
    print(f"\nSaved: {out_path}")


def run_delete(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf = resolve_pdffile(args.pdffile)
    doc = fitz.open(str(pdf))

    if not args.pages:
        print(
            "Error: --pages is required for delete (example: 1,2,5-10).",
            file=sys.stderr,
        )
        doc.close()
        sys.exit(1)

    page_numbers = parse_page_ranges(args.pages, len(doc))
    if len(page_numbers) == len(doc):
        print("Error: delete cannot remove all pages.", file=sys.stderr)
        doc.close()
        sys.exit(1)

    for p in sorted(page_numbers, reverse=True):
        doc.delete_page(p - 1)

    out_path = resolve_output_path(args.outfile, pdf)
    doc.save(str(out_path))
    doc.close()
    print(f"\nSaved: {out_path}")


def run_replace(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf1 = resolve_pdffile(args.pdffile)
    pdf2 = resolve_pdffile2(args.pdffile2)

    target_doc = fitz.open(str(pdf1))
    source_doc = fitz.open(str(pdf2))

    target_page = resolve_page(args.page, len(target_doc))
    source_page = resolve_page(args.sourcepage, len(source_doc))

    target_idx = target_page - 1
    source_idx = source_page - 1

    target_doc.delete_page(target_idx)
    target_doc.insert_pdf(
        source_doc,
        from_page=source_idx,
        to_page=source_idx,
        start_at=target_idx,
    )

    out_path = resolve_output_path(args.outfile, pdf1)
    target_doc.save(str(out_path))
    source_doc.close()
    target_doc.close()
    print(f"\nSaved: {out_path}")


def run_insert(args: argparse.Namespace) -> None:
    """Alias of replace operation for friendlier naming in docs/CLI."""
    run_replace(args)


def run_protect(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf = resolve_pdffile(args.pdffile)
    doc = fitz.open(str(pdf))

    out_path = resolve_output_path(args.outfile, pdf)

    encrypt_aes_256 = int(getattr(fitz, "PDF_ENCRYPT_AES_256", 5))
    perm_print = int(getattr(fitz, "PDF_PERM_PRINT", 4))
    perm_accessibility = int(getattr(fitz, "PDF_PERM_ACCESSIBILITY", 512))

    if args.protectmode == "permissions":
        owner_pw = resolve_password(args.ownerpassword or args.password)
        perms = int(perm_print | perm_accessibility)
        doc.save(
            str(out_path),
            encryption=encrypt_aes_256,
            owner_pw=owner_pw,
            user_pw="",
            permissions=perms,
        )
    else:
        user_pw = resolve_password(args.password)
        owner_pw = args.ownerpassword or user_pw
        doc.save(
            str(out_path),
            encryption=encrypt_aes_256,
            owner_pw=owner_pw,
            user_pw=user_pw,
        )

    doc.close()
    print(f"\nSaved: {out_path}")


def run_unprotect(args: argparse.Namespace) -> None:
    try:
        import fitz
    except ImportError:
        print(
            "Error: PyMuPDF (pymupdf) is not installed. Run: uv sync", file=sys.stderr
        )
        sys.exit(1)

    pdf = resolve_pdffile(args.pdffile)
    doc = fitz.open(str(pdf))

    if doc.needs_pass:
        password = resolve_password(args.password)
        if not doc.authenticate(password):
            print("Error: Invalid password for encrypted PDF.", file=sys.stderr)
            doc.close()
            sys.exit(1)

    encrypt_none = int(getattr(fitz, "PDF_ENCRYPT_NONE", 1))
    out_path = resolve_output_path(args.outfile, pdf)
    doc.save(str(out_path), encryption=encrypt_none)
    doc.close()
    print(f"\nSaved: {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PDFEdit CLI for stamp, merge, append, rotate, delete, and replace operations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pdffile", help="PDF file (name inside input-pdf/ or full path)"
    )
    parser.add_argument(
        "--operation",
        choices=[
            "stamp",
            "merge",
            "append",
            "rotate",
            "delete",
            "replace",
            "insert",
            "protect",
            "unprotect",
        ],
        default="stamp",
        help="PDF operation to run (default: stamp)",
    )
    parser.add_argument(
        "--pdffile2",
        help="Secondary PDF for merge/append/replace (name in input-pdf/ or full path)",
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
    parser.add_argument(
        "--pages",
        help="Page selection expression, e.g. '1, 2, 3, 5-10, 12-15, 20, 45'",
    )
    parser.add_argument(
        "--direction",
        choices=["cw", "ccw"],
        default="cw",
        help="Rotation direction for rotate operation (default: cw)",
    )
    parser.add_argument(
        "--sourcepage",
        type=int,
        help="Page number from secondary PDF used by replace",
    )
    parser.add_argument(
        "--backsideorder",
        choices=["reverse", "normal"],
        default="reverse",
        help="Page order of secondary scan in merge (default: reverse)",
    )
    parser.add_argument(
        "--outfile",
        help="Output PDF filename or path (default: output-pdf/<pdffile name>)",
    )
    parser.add_argument(
        "--protectmode",
        choices=["permissions", "encrypt"],
        default="permissions",
        help="Mode for protect: permissions (no open password) or encrypt (requires open password)",
    )
    parser.add_argument(
        "--password",
        help="Password for protect/encrypt or unprotect; defaults to PDFEDIT_DEFAULT_PASSWORD from .env",
    )
    parser.add_argument(
        "--ownerpassword",
        help="Owner password override for protect operation",
    )

    args = parser.parse_args()

    operation_dispatch = {
        "stamp": run_stamp,
        "merge": run_merge,
        "append": run_append,
        "rotate": run_rotate,
        "delete": run_delete,
        "replace": run_replace,
        "insert": run_insert,
        "protect": run_protect,
        "unprotect": run_unprotect,
    }
    operation_dispatch[args.operation](args)


if __name__ == "__main__":
    main()
