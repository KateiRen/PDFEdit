# PDFEdit MCP Contract

This document defines the MCP tool contract for the local PDFEdit server.

## Transport and Scope

- Transport: local stdio (client spawns server process)
- Trust model: local machine usage
- Backend execution: each MCP tool invokes main.py with --non-interactive

## File Input and Output Model

### Inputs

Input files are provided as path strings in tool arguments:

- pdffile
- pdffile2 (where required)
- gfxfile (stamp)

Path resolution follows the existing CLI behavior:

- Relative paths are resolved under input-pdf or input-gfx where applicable
- Absolute paths are accepted

### Outputs

Each tool accepts optional outfile.

- If outfile is omitted, the server generates a unique filename under output-pdf
- The server returns output_file as an absolute path

## Common Response Shape

Every tool returns a JSON object with this shape:

- ok: boolean
- operation: string
- exit_code: integer
- output_file: absolute path or null
- stdout: string
- stderr: string

Success criteria:

- ok = true
- exit_code = 0
- output_file exists

## Tools

### stamp

Inputs:

- pdffile: string (required)
- gfxfile: string (required)
- posX: number (required)
- posY: number (required)
- page: integer (required)
- width: number (optional)
- height: number (optional)
- insertmode: string (optional, normal|darken, default normal)
- outfile: string (optional)

### merge

Inputs:

- pdffile: string (required)
- pdffile2: string (required)
- backsideorder: string (optional, reverse|normal, default reverse)
- outfile: string (optional)

### append

Inputs:

- pdffile: string (required)
- pdffile2: string (required)
- outfile: string (optional)

### rotate

Inputs:

- pdffile: string (required)
- direction: string (optional, cw|ccw, default cw)
- pages: string (optional, e.g. 1,2,5-10)
- outfile: string (optional)

### delete

Inputs:

- pdffile: string (required)
- pages: string (required, e.g. 1,2,5-10)
- outfile: string (optional)

### replace

Inputs:

- pdffile: string (required)
- pdffile2: string (required)
- page: integer (required)
- sourcepage: integer (required)
- outfile: string (optional)

### insert

Alias of replace. Same arguments.

### protect

Inputs:

- pdffile: string (required)
- protectmode: string (optional, permissions|encrypt, default permissions)
- password: string (optional)
- ownerpassword: string (optional)
- outfile: string (optional)

Note:

- In non-interactive mode, passwords must come from argument or PDFEDIT_DEFAULT_PASSWORD in .env.

### unprotect

Inputs:

- pdffile: string (required)
- password: string (optional)
- outfile: string (optional)

## Error Behavior

- Validation/runtime issues return ok=false with stderr populated
- Tool execution timeout returns ok=false with exit_code=124
- MCP tools do not raise interactive prompts

## Security Notes

- Password values are accepted as inputs but not echoed back in responses
- permissions mode is a best-effort viewer restriction, not guaranteed prevention of extraction
- stamp is a visual mark and not a cryptographic digital signature
