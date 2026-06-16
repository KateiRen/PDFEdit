# PDFEdit

Simple Python CLI to place a JPG/PNG graphic onto an existing PDF.

## Common scenario

You've filled out a PDF form digitally, but now you need to add a handwritten signature. Normally this means: print -> sign by hand -> scan -> send/upload the signed file.

PDFEdit eliminates the print-sign-scan cycle. Sign on a tablet or phone, save as PNG, and use this tool to place it directly onto your PDF form while keeping everything digital.

One step closer to a paperless office. 👍

---

It supports:
- interactive mode (ask for missing values)
- command-line mode (fully scripted)
- non-interactive mode (`--non-interactive`) for automation/MCP
- proportional scaling when only width or height is provided
- operation-based processing:
	- `stamp`
	- `merge`
	- `append`
	- `rotate`
	- `delete`
	- `replace` / `insert` (alias)
	- `protect` / `unprotect`
- two insert modes for `stamp`:
	- `normal`: direct overlay
	- `darken`: only darker graphic pixels affect the PDF


## Supported Operations

### Stamp

Places an image (signature/logo) on a specific page at a defined position and size.

Important:
- stamp adds a visual mark only
- it does not create a cryptographic/digital PDF signature

### Merge

Combines two scan runs into one two-sided document by interleaving pages from file 1 and file 2.

Typical use case: front sides in one PDF and back sides in another PDF.

Back-side order is configurable via `--backsideorder`:
- `reverse` (default): uses last page to first page from file 2
- `normal`: uses first page to last page from file 2

### Append

Adds all pages from file 2 to the end of file 1.

### Rotate

Rotates pages by 90 degrees clockwise (`cw`) or counter-clockwise (`ccw`).

You can rotate:
- all pages (omit `--pages`)
- selected pages/ranges using `--pages`

Supported page expression format:
`1, 2, 3, 5-10, 12-15, 20, 45`

### Delete

Removes selected pages from a PDF using the same `--pages` expression format as rotate.

Supported page expression format:
`1, 2, 3, 5-10, 12-15, 20, 45`

### Replace / Insert

Replaces one page in file 1 with one page from file 2.

`insert` is an alias of `replace` in the CLI.

### Protect / Unprotect

Protect and unprotect PDF security settings.

Protect modes:
- `permissions`: opens without user password, but disables copy/extract in compliant viewers
- `encrypt`: requires a password to open the PDF

Password behavior:
- default password is read from `.env` key `PDFEDIT_DEFAULT_PASSWORD`
- you can override at runtime with `--password`
- optional separate owner password via `--ownerpassword`

Unprotect:
- removes PDF encryption/security from a file
- if input is encrypted, provide `--password` (or `.env` default)

Security disclaimer:
- permissions mode helps against casual copying/extraction in compliant viewers
- it does not guarantee that content cannot be extracted by determined users/tools


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
	--operation stamp \
	--pdffile "document.pdf" \
	--gfxfile "signature.png" \
	--posX 140 \
	--posY 245 \
	--width 60 \
	--page 1 \
	--insertmode darken
```

### Non-interactive mode (automation-safe)

Use `--non-interactive` to disable all prompts. Missing required inputs fail fast.

```bash
uv run python main.py \
	--non-interactive \
	--operation stamp \
	--pdffile "document.pdf" \
	--gfxfile "signature.png" \
	--posX 140 \
	--posY 245 \
	--page 1
```

## MCP Server

PDFEdit includes a local MCP server that exposes each supported operation as a tool and executes `main.py` with `--non-interactive`.

### Transport and runtime

- Transports: `stdio` (local process) and `streamable-http` (URL endpoint)
- Server entrypoint: `mcp_server.py`
- Tool contract: `docs/mcp-contract.md`

Start in stdio mode (default):

```bash
uv run python mcp_server.py
```

Start in HTTP mode (for URL-based MCP clients):

```bash
uv run python mcp_server.py --transport streamable-http
```

Default HTTP endpoint URL:

`http://127.0.0.1:3000/mcp`

Optional env overrides for HTTP mode:

- `PDFEDIT_MCP_HOST` (default: `127.0.0.1`)
- `PDFEDIT_MCP_PORT` (default: `3000`)
- `PDFEDIT_MCP_HTTP_PATH` (default: `/mcp`)

### Client configuration model

For MCP clients that support stdio servers, configure command/args/cwd similar to:

```json
{
	"name": "pdfedit",
	"command": "uv",
	"args": ["run", "python", "mcp_server.py"],
	"cwd": "<absolute-path-to-project>"
}
```

### File input and output behavior

- Tool inputs are file path strings (`pdffile`, `pdffile2`, `gfxfile`).
- Relative file names are resolved by the CLI as documented (for example `input-pdf/`, `input-gfx/`).
- Each tool accepts optional `outfile`.
- If `outfile` is omitted, the MCP server generates a unique PDF filename in `output-pdf/`.
- Tool responses include `output_file` so clients can open/download the produced file.

### Response shape

Each tool returns a structured payload containing:

- `ok`
- `operation`
- `exit_code`
- `output_file`
- `stdout`
- `stderr`

### Password/secrets in MCP mode

- MCP calls are non-interactive by design.
- For `protect`/`unprotect`, provide `password` explicitly, or set `PDFEDIT_DEFAULT_PASSWORD` in `.env`.
- Hidden terminal prompts are only used in direct CLI runs without `--non-interactive`.

### Quick validation

Run the bundled smoke test (starts local server, calls `stamp`, verifies `output_file` exists):

```bash
uv run python scripts/mcp_smoke_test.py
```

## Arguments

- `--pdffile` PDF filename (or full path)
- `--operation` one of `stamp`, `merge`, `append`, `rotate`, `delete`, `replace`, `insert`, `protect`, `unprotect` (default: `stamp`)
- `--pdffile2` secondary PDF for `merge`, `append`, `replace`/`insert`
- `--gfxfile` image filename (or full path)
- `--posX` X position in mm
- `--posY` Y position in mm
- `--width` width in mm (optional)
- `--height` height in mm (optional)
- `--page` page number, 1-based
- `--insertmode` one of `normal` or `darken` (default: `normal`)
- `--pages` page expression for `rotate` and `delete` (example: `1,2,5-10`)
- `--direction` `cw` or `ccw` for `rotate` (default: `cw`)
- `--sourcepage` page in `--pdffile2` used by `replace`/`insert`
- `--backsideorder` page order mode for `merge`: `reverse` (default) or `normal`
- `--outfile` output PDF filename/path (default: `output-pdf/<pdffile name>`)
- `--protectmode` mode for `protect`: `permissions` (default) or `encrypt`
- `--password` password for `protect`/`unprotect` (falls back to `.env`, then hidden prompt)
- `--ownerpassword` optional owner password for `protect`
- `--non-interactive` disable all prompts and fail on missing required inputs

## Operation Examples

### Stamp (signature/logo)

```bash
uv run python main.py \
	--operation stamp \
	--pdffile "form.pdf" \
	--gfxfile "signature.png" \
	--posX 140 \
	--posY 245 \
	--width 60 \
	--page 1 \
	--insertmode darken \
	--outfile "form-signed.pdf"
```

### Merge (duplex scan merge)

```bash
uv run python main.py \
	--operation merge \
	--pdffile "scan-front.pdf" \
	--pdffile2 "scan-back.pdf" \
	--backsideorder reverse \
	--outfile "scan-merged.pdf"
```

### Append

```bash
uv run python main.py \
	--operation append \
	--pdffile "contract.pdf" \
	--pdffile2 "annex.pdf" \
	--outfile "contract-with-annex.pdf"
```

### Rotate (selected pages/ranges)

```bash
uv run python main.py \
	--operation rotate \
	--pdffile "scan.pdf" \
	--direction cw \
	--pages "1, 2, 3, 5-10, 12-15, 20, 45" \
	--outfile "scan-rotated.pdf"
```

### Delete (selected pages/ranges)

```bash
uv run python main.py \
	--operation delete \
	--pdffile "report.pdf" \
	--pages "2, 4, 7-9" \
	--outfile "report-clean.pdf"
```

### Replace / Insert (alias)

```bash
uv run python main.py \
	--operation replace \
	--pdffile "doc-main.pdf" \
	--pdffile2 "doc-patch.pdf" \
	--page 5 \
	--sourcepage 1 \
	--outfile "doc-updated.pdf"
```

### Protect (permissions mode, no open password)

```bash
uv run python main.py \
	--operation protect \
	--pdffile "doc.pdf" \
	--protectmode permissions \
	--outfile "doc-protected.pdf"
```

### Protect (encrypt mode, open password required)

```bash
uv run python main.py \
	--operation protect \
	--pdffile "doc.pdf" \
	--protectmode encrypt \
	--password "MyOpenPassword" \
	--outfile "doc-encrypted.pdf"
```

### Unprotect

```bash
uv run python main.py \
	--operation unprotect \
	--pdffile "doc-encrypted.pdf" \
	--password "MyOpenPassword" \
	--outfile "doc-unprotected.pdf"
```

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

`--insertmode` currently applies to the `stamp` operation.

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
