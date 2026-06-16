from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).parent
CLI_MAIN = PROJECT_ROOT / "main.py"
OUTPUT_DIR = PROJECT_ROOT / "output-pdf"

HTTP_HOST = os.getenv("PDFEDIT_MCP_HOST", "127.0.0.1")
HTTP_PORT = int(os.getenv("PDFEDIT_MCP_PORT", "3000"))
HTTP_PATH = os.getenv("PDFEDIT_MCP_HTTP_PATH", "/mcp")

mcp = FastMCP(
    "pdfedit",
    host=HTTP_HOST,
    port=HTTP_PORT,
    streamable_http_path=HTTP_PATH,
)


def _abs_output_path(outfile: str) -> Path:
    p = Path(outfile)
    if not p.is_absolute():
        p = OUTPUT_DIR / p
    return p.resolve()


def _default_outfile(operation: str) -> str:
    return f"{operation}-{uuid.uuid4().hex}.pdf"


async def _run_cli(
    operation: str,
    *,
    outfile: str | None = None,
    timeout_sec: int = 60,
    **kwargs: Any,
) -> dict[str, Any]:
    effective_out = outfile or _default_outfile(operation)

    cmd: list[str] = [
        sys.executable,
        str(CLI_MAIN),
        "--non-interactive",
        "--operation",
        operation,
        "--outfile",
        effective_out,
    ]

    for key, value in kwargs.items():
        if value is None:
            continue
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                cmd.append(flag)
            continue
        cmd.extend([flag, str(value)])

    out_path = _abs_output_path(effective_out)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        raw_stdout, raw_stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return {
            "ok": False,
            "operation": operation,
            "exit_code": 124,
            "output_file": None,
            "stdout": "",
            "stderr": f"Command timed out after {timeout_sec}s.",
        }

    stdout = raw_stdout.decode("utf-8", errors="replace").strip()
    stderr = raw_stderr.decode("utf-8", errors="replace").strip()
    ok = proc.returncode == 0 and out_path.exists()
    return {
        "ok": ok,
        "operation": operation,
        "exit_code": proc.returncode,
        "output_file": str(out_path) if out_path.exists() else None,
        "stdout": stdout,
        "stderr": stderr,
    }


@mcp.tool()
async def stamp(
    pdffile: str,
    gfxfile: str,
    posX: float,
    posY: float,
    page: int,
    width: float | None = None,
    height: float | None = None,
    insertmode: str = "normal",
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "stamp",
        pdffile=pdffile,
        gfxfile=gfxfile,
        posX=posX,
        posY=posY,
        page=page,
        width=width,
        height=height,
        insertmode=insertmode,
        outfile=outfile,
    )


@mcp.tool()
async def merge(
    pdffile: str,
    pdffile2: str,
    backsideorder: str = "reverse",
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "merge",
        pdffile=pdffile,
        pdffile2=pdffile2,
        backsideorder=backsideorder,
        outfile=outfile,
    )


@mcp.tool()
async def append(
    pdffile: str,
    pdffile2: str,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "append",
        pdffile=pdffile,
        pdffile2=pdffile2,
        outfile=outfile,
    )


@mcp.tool()
async def rotate(
    pdffile: str,
    direction: str = "cw",
    pages: str | None = None,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "rotate",
        pdffile=pdffile,
        direction=direction,
        pages=pages,
        outfile=outfile,
    )


@mcp.tool()
async def delete(
    pdffile: str,
    pages: str,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli("delete", pdffile=pdffile, pages=pages, outfile=outfile)


@mcp.tool()
async def replace(
    pdffile: str,
    pdffile2: str,
    page: int,
    sourcepage: int,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "replace",
        pdffile=pdffile,
        pdffile2=pdffile2,
        page=page,
        sourcepage=sourcepage,
        outfile=outfile,
    )


@mcp.tool()
async def insert(
    pdffile: str,
    pdffile2: str,
    page: int,
    sourcepage: int,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "insert",
        pdffile=pdffile,
        pdffile2=pdffile2,
        page=page,
        sourcepage=sourcepage,
        outfile=outfile,
    )


@mcp.tool()
async def protect(
    pdffile: str,
    protectmode: str = "permissions",
    password: str | None = None,
    ownerpassword: str | None = None,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "protect",
        pdffile=pdffile,
        protectmode=protectmode,
        password=password,
        ownerpassword=ownerpassword,
        outfile=outfile,
    )


@mcp.tool()
async def unprotect(
    pdffile: str,
    password: str | None = None,
    outfile: str | None = None,
) -> dict[str, Any]:
    return await _run_cli(
        "unprotect",
        pdffile=pdffile,
        password=password,
        outfile=outfile,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PDFEdit MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport mode (default: stdio)",
    )
    parser.add_argument(
        "--mount-path",
        default=None,
        help="Optional mount path when running HTTP transports",
    )

    args = parser.parse_args()
    mcp.run(transport=args.transport, mount_path=args.mount_path)
