#!/bin/sh
# Install ptk on Linux/macOS: uv (if missing) + ptk as a uv tool.
#
#   curl -LsSf <url>/install.sh | sh
#   PTK_SOURCE="git+https://github.com/<org>/ptk@v0.1.0" sh install.sh
#   sh install.sh --no-extension     install the CLI without changing VS Code
#   sh install.sh --force-extension  reinstall/downgrade the bundled extension
#   sh install.sh --no-completion    leave shell completion profiles unchanged
#
# Environment:
#   PTK_SOURCE   what 'uv tool install' installs (default: this checkout, otherwise ptk from your index)
#   PTK_EXTRAS   optional extras, e.g. "keyring"
#   UV_INDEX_URL / UV_EXTRA_INDEX_URL   your package index (standard uv variables)
set -eu

say() { printf 'ptk-install: %s\n' "$*"; }

no_extension=0
no_completion=0
force_extension=0
for option in "$@"; do
    case "$option" in
        --no-extension) no_extension=1 ;;
        --no-completion) no_completion=1 ;;
        --force-extension) force_extension=1 ;;
        *) say "unknown option: $option (use --no-extension, --force-extension or --no-completion)"; exit 2 ;;
    esac
done

if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        PATH="$HOME/.local/bin:$PATH"
    else
        say "installing uv (https://docs.astral.sh/uv/)"
        if command -v curl >/dev/null 2>&1; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        elif command -v wget >/dev/null 2>&1; then
            wget -qO- https://astral.sh/uv/install.sh | sh
        else
            say "need curl or wget to install uv"; exit 1
        fi
        PATH="$HOME/.local/bin:$PATH"
    fi
fi

source="${PTK_SOURCE:-}"
if [ -z "$source" ]; then
    source=ptk
    # A downloaded/piped standalone script has no checkout to install.
    if [ -f "$0" ]; then
        script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
        checkout=$(CDPATH= cd -- "$script_dir/.." && pwd)
        if [ -f "$checkout/pyproject.toml" ] && [ -d "$checkout/src/ptk" ]; then
            source="$checkout"
            force_extension=1
        fi
    fi
fi
if [ -n "${PTK_EXTRAS:-}" ]; then
    case "$source" in
        *://*|*@*) say "PTK_EXTRAS is ignored for URL sources" ;;
        *) source="$source[$PTK_EXTRAS]" ;;
    esac
fi

say "installing/updating $source"
# Reinstall even when the package version is unchanged; refresh resolution too.
uv tool install --force --reinstall --upgrade --python 3.12 "$source"
uv tool update-shell >/dev/null 2>&1 || true

if [ "$no_extension" = 0 ] || [ "$no_completion" = 0 ]; then
    tool_bin=$(uv tool dir --bin)
    # Git Bash receives a Windows path from the native uv executable.
    if command -v cygpath >/dev/null 2>&1; then tool_bin=$(cygpath -u "$tool_bin"); fi
    ptk_executable="$tool_bin/ptk"
    if [ -f "$tool_bin/ptk.exe" ]; then ptk_executable="$tool_bin/ptk.exe"; fi
    if [ ! -x "$ptk_executable" ]; then say "PTK installed, but cannot find its executable in $tool_bin"; exit 1; fi
fi
if [ "$no_extension" = 0 ]; then
    set -- self-service extension --if-available
    if [ "$force_extension" = 1 ]; then set -- "$@" --force; fi
    if ! "$ptk_executable" "$@"; then
        say 'PTK installed, but extension setup failed; retry: ptk self-service extension'
        exit 1
    fi
fi

if [ "$no_completion" = 0 ]; then
    if ! "$ptk_executable" self-service completion install --executable "$ptk_executable"; then
        say 'PTK installed, but completion setup failed; retry: ptk self-service completion install'
        exit 1
    fi
fi

say "done - open a new terminal, then run: ptk self-service doctor"
