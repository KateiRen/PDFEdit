# PDFEdit

Simple Python CLI to place a JPG/PNG graphic onto an existing PDF.

## Common scenario

You've filled out a PDF form digitally, but now you need to add a handwritten signature. Normally this means: print -> sign by hand -> scan -> insert into PDF.

PDFEdit eliminates the print-sign-scan cycle. Sign on a tablet or phone, save as PNG, and use this tool to place it directly onto your PDF form while keeping everything digital.

One step closer to a paperless office. 👍

---

It supports:
- interactive mode (ask for missing values)
- command-line mode (fully scripted)
- proportional scaling when only width or height is provided
- two insert modes:
	- `normal`: direct overlay
	- `darken`: only darker graphic pixels affect the PDF

## Folder Structure

```text
input-pdf/   source PDF files
input-gfx/   source images (.jpg/.jpeg/.png)
output-pdf/  generated PDFs (same filename as source PDF)
```

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended)

## Install

```bash
uv sync --all-extras
```

This installs runtime deps (`pymupdf`, `pillow`) and dev deps (`pre-commit`).

## Usage

### Interactive mode

Run without arguments. The program will:
- list PDFs from `input-pdf/`
- list images from `input-gfx/`
- ask for page, position and size values

```bash
uv run python main.py
```

After a successful interactive run, the tool prints an equivalent full command.

### Command-line mode

```bash
uv run python main.py \
	--pdffile "document.pdf" \
	--gfxfile "signature.png" \
	--posX 140 \
	--posY 245 \
	--width 60 \
	--page 1 \
	--insertmode darken
```

## Arguments

- `--pdffile` PDF filename (or full path)
- `--gfxfile` image filename (or full path)
- `--posX` X position in mm
- `--posY` Y position in mm
- `--width` width in mm (optional)
- `--height` height in mm (optional)
- `--page` page number, 1-based
- `--insertmode` one of `normal` or `darken` (default: `normal`)

### Coordinate system

- Units: millimeters
- Origin: top-left of the page
- Positive X: right
- Positive Y: down

### Sizing behavior

- if both `width` and `height` are set: use both
- if only one is set: keep aspect ratio
- if neither is set: use the image's original size

## Insert Modes

### `normal`

Directly inserts the image in the target rectangle.

### `darken`

Blends image and PDF pixels using darken logic (channel-wise minimum):

`result = min(pdf_pixel, gfx_pixel)`

This is useful for signatures on light form backgrounds because bright image background areas usually do not lighten the PDF content.

## Output

Result is saved to:

`output-pdf/<same_pdf_filename>.pdf`

Example:
- input: `input-pdf/form.pdf`
- output: `output-pdf/form.pdf`


## Pre-commit and Safety

This repo is configured with pre-commit hooks.

Install hook:

```bash
uv run pre-commit install
```

Run checks manually:

```bash
uv run pre-commit run --all-files
```

Current checks include:
- formatting and whitespace checks
- TOML/YAML sanity checks
- large-file check
- private-key and secret scanning
- Ruff lint/format
- blocking committed media/doc files: `*.pdf`, `*.jpg`, `*.jpeg`, `*.png`
