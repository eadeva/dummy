# Install ptk on Windows: uv (if missing) + ptk as a uv tool.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   $env:PTK_SOURCE = "git+https://github.com/<org>/ptk@v0.1.0"; .\install.ps1
#
# Environment:
#   PTK_SOURCE   what 'uv tool install' installs (default: this checkout, otherwise ptk from your index)
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

$source = $env:PTK_SOURCE
if (-not $source) {
    $source = "ptk"
    if ($PSScriptRoot) {
        $checkout = Split-Path -Parent $PSScriptRoot
        if ((Test-Path (Join-Path $checkout "pyproject.toml")) -and
            (Test-Path (Join-Path $checkout "src/ptk") -PathType Container)) {
            $source = $checkout
        }
    }
}
if ($env:PTK_EXTRAS) {
    if ($source -match "://|@") { Say "PTK_EXTRAS is ignored for URL sources" }
    else { $source = "$source[$($env:PTK_EXTRAS)]" }
}

Say "installing/updating $source"
# Reinstall even when the package version is unchanged; refresh resolution too.
uv tool install --force --reinstall --upgrade --python 3.12 $source
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed" }
uv tool update-shell | Out-Null

Say "done - open a new terminal, then run: ptk setup doctor"
