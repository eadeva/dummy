# Install ptk on Windows: uv (if missing) + ptk as a uv tool.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   $env:PTK_SOURCE = "git+https://github.com/<org>/ptk@v0.1.0"; .\install.ps1
#   .\install.ps1 -NoCompletion   leave completion and profiles unchanged
#   .\install.ps1 -NoExtension    install the CLI without changing VS Code
#   .\install.ps1 -ForceExtension reinstall/downgrade the bundled extension explicitly
#
# Environment:
#   PTK_SOURCE   what 'uv tool install' installs (default: this checkout, otherwise ptk from your index)
#   PTK_EXTRAS   optional extras, e.g. "keyring" (Windows Credential Manager)
#   UV_INDEX_URL / UV_EXTRA_INDEX_URL   your package index (standard uv variables)
param([switch]$NoCompletion, [switch]$NoExtension, [switch]$ForceExtension)

$ErrorActionPreference = "Stop"

function Say($text) { Write-Host "ptk-install: $text" }

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    $local = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path $local) {
        $env:PATH = (Split-Path $local) + ";" + $env:PATH
    } else {
        Say "installing uv (https://docs.astral.sh/uv/)"
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        $env:PATH = (Join-Path $env:USERPROFILE ".local\bin") + ";" + $env:PATH
    }
}

$source = $env:PTK_SOURCE
$fromCheckout = $false
if (-not $source) {
    $source = "ptk"
    if ($PSScriptRoot) {
        $checkout = Split-Path -Parent $PSScriptRoot
        if ((Test-Path (Join-Path $checkout "pyproject.toml")) -and
            (Test-Path (Join-Path $checkout "src/ptk") -PathType Container)) {
            $source = $checkout
            $fromCheckout = $true
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
if ($LASTEXITCODE -ne 0) { Write-Warning "uv could not update the shell PATH; completion setup will also add the tool directory to supported shell profiles." }

if (-not $NoCompletion -or -not $NoExtension) {
    $toolBin = (uv tool dir --bin | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $toolBin) { throw "PTK installed, but cannot locate uv's tool directory" }
    $ptkExecutable = Join-Path $toolBin "ptk.exe"
    if (-not (Test-Path -LiteralPath $ptkExecutable -PathType Leaf)) { throw "ptk.exe not found in $toolBin" }
    $env:PATH = $toolBin + [IO.Path]::PathSeparator + $env:PATH
}

if (-not $NoExtension) {
    # A checkout rebuild must refresh same-version extension code during development.
    $extensionOptions = @("setup", "extension", "--if-available")
    if ($ForceExtension -or $fromCheckout) { $extensionOptions += "--force" }
    & $ptkExecutable @extensionOptions
    if ($LASTEXITCODE -ne 0) { throw "PTK installed, but extension setup failed; retry: ptk setup extension" }
}

if (-not $NoCompletion) {
    try {
        # Use the tool just installed, even if an older ptk is active in a venv.
        & $ptkExecutable setup completion install --executable $ptkExecutable --powershell-profile $PROFILE.CurrentUserAllHosts
        if ($LASTEXITCODE -ne 0) { throw "could not update shell profiles" }
        $completionScript = & $ptkExecutable setup completion powershell --double-tab | Out-String
        if ($LASTEXITCODE -ne 0) { throw "could not generate completion" }
        Invoke-Expression $completionScript
        Say "Tab completion enabled now and in future PowerShell and Bash/Git Bash terminals"
        Say "double-Tab listing applies to all commands; profile: $($PROFILE.CurrentUserAllHosts)"
    } catch {
        Write-Warning "PTK is installed, but completion setup failed: $_"
        Say 'retry: ptk setup completion install'
    }
}

Say "done - run: ptk setup doctor"
