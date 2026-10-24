# Install ptk on Windows: uv (if missing) + ptk as a uv tool.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   $env:PTK_SOURCE = "git+https://github.com/<org>/ptk@v0.1.0"; .\install.ps1
#
# Environment:
#   PTK_SOURCE   what 'uv tool install' installs (default: ptk, e.g. from your index)
#   PTK_EXTRAS   optional extras, e.g. "keyring" (Windows Credential Manager)
#   UV_INDEX_URL / UV_EXTRA_INDEX_URL   your package index (standard uv variables)
$ErrorActionPreference = "Stop"

function Say($text) { Write-Host "ptk-install: $text" }

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    $local = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $local) {
        $env:Path = (Split-Path $local) + ";" + $env:Path
    } else {
        Say "installing uv (https://docs.astral.sh/uv/)"
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $env:Path = (Join-Path $env:USERPROFILE ".local\bin") + ";" + $env:Path
    }
}

$source = if ($env:PTK_SOURCE) { $env:PTK_SOURCE } else { "ptk" }
if ($env:PTK_EXTRAS) {
    if ($source -match "://|@") { Say "PTK_EXTRAS is ignored for URL sources" }
    else { $source = "$source[$($env:PTK_EXTRAS)]" }
}

Say "installing $source"
uv tool install --force --python 3.12 $source
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed" }
uv tool update-shell | Out-Null

Say "done - open a new terminal, then run: ptk doctor"
