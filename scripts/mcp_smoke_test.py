"""Minimal MCP stdio client smoke test for PDFEdit.

Starts the local MCP server via stdio, calls one tool (`stamp` by default),
and verifies that the returned output file exists.
"""

from __future__ import annotations

import argparse
import anyio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PDF_DIR = PROJECT_ROOT / "input-pdf"
INPUT_GFX_DIR = PROJECT_ROOT / "input-gfx"


def _pick_first(path: Path, pattern: str) -> Path:
    candidates = sorted(p for p in path.glob(pattern) if p.name != ".gitkeep")
    if not candidates:
        raise FileNotFoundError(f"No files matching '{pattern}' in {path}")
    return candidates[0]


def _extract_tool_payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured

    content = getattr(result, "content", None) or []
    if isinstance(content, list) and content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {"ok": False, "raw_text": text}
            if isinstance(parsed, dict):
                return parsed

    if isinstance(result, dict):
        return dict(result)

    return {"ok": False, "raw": result}


async def run_smoke_test(pdffile: str, gfxfile: str, outfile: str | None) -> int:
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_ROOT / "mcp_server.py")],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "UV_LINK_MODE": os.getenv("UV_LINK_MODE", "copy")},
    )

    print("[smoke] starting stdio client...")
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("[smoke] initializing session...")
            with anyio.fail_after(20):
                await session.initialize()

            print("[smoke] listing tools...")
            with anyio.fail_after(20):
                tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"[smoke] tools: {', '.join(tool_names)}")

            print("[smoke] calling stamp tool...")
            with anyio.fail_after(60):
                tool_result = await session.call_tool(
                    "stamp",
                    arguments={
                        "pdffile": pdffile,
                        "gfxfile": gfxfile,
                        "posX": 10,
                        "posY": 10,
                        "page": 1,
                        "width": 30,
                        "insertmode": "normal",
                        "outfile": outfile,
                    },
                )

            payload = _extract_tool_payload(tool_result)
            print(json.dumps(payload, indent=2, ensure_ascii=False))

            output_file = payload.get("output_file")
            if not payload.get("ok"):
                print("Smoke test failed: tool returned ok=false.")
                return 1
            if not output_file or not Path(output_file).exists():
                print("Smoke test failed: output_file missing or does not exist.")
                return 1

            print(f"Smoke test passed. Output: {output_file}")
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a minimal MCP smoke test against local mcp_server.py"
    )
    parser.add_argument(
        "--pdffile",
        help="Input PDF filename/path (default: first file in input-pdf)",
    )
    parser.add_argument(
        "--gfxfile",
        help="Input image filename/path (default: first .png/.jpg in input-gfx)",
    )
    parser.add_argument(
        "--outfile",
        default="mcp-smoke-output.pdf",
        help="Output PDF filename/path returned by the tool",
    )
    args = parser.parse_args()

    pdffile = args.pdffile or _pick_first(INPUT_PDF_DIR, "*.pdf").name

    if args.gfxfile:
        gfxfile = args.gfxfile
    else:
        try:
            gfxfile = _pick_first(INPUT_GFX_DIR, "*.png").name
        except FileNotFoundError:
            gfxfile = _pick_first(INPUT_GFX_DIR, "*.jpg").name

    return anyio.run(
        run_smoke_test,
        pdffile,
        gfxfile,
        args.outfile,
    )


if __name__ == "__main__":
    raise SystemExit(main())
