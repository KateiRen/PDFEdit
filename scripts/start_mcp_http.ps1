param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 3000,
    [string]$McpPath = "/mcp"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed or not in PATH. Install uv first."
    exit 1
}

$projectRoot = Split-Path -Parent $PSScriptRoot

$env:UV_LINK_MODE = "copy"
$env:PDFEDIT_MCP_HOST = $HostAddress
$env:PDFEDIT_MCP_PORT = [string]$Port
$env:PDFEDIT_MCP_HTTP_PATH = $McpPath

Write-Host "Starting PDFEdit MCP HTTP server..." -ForegroundColor Cyan
Write-Host "Endpoint: http://$HostAddress`:$Port$McpPath" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow

Set-Location $projectRoot
uv run python mcp_server.py --transport streamable-http
