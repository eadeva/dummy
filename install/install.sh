#!/bin/sh
# Install ptk on Linux/macOS: uv (if missing) + ptk as a uv tool.
#
#   curl -LsSf <url>/install.sh | sh
#   PTK_SOURCE="git+https://github.com/<org>/ptk@v0.1.0" sh install.sh
#
# Environment:
#   PTK_SOURCE   what 'uv tool install' installs (default: ptk, e.g. from your index)
#   PTK_EXTRAS   optional extras, e.g. "keyring"
#   UV_INDEX_URL / UV_EXTRA_INDEX_URL   your package index (standard uv variables)
set -eu

say() { printf 'ptk-install: %s\n' "$*"; }

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

source="${PTK_SOURCE:-ptk}"
if [ -n "${PTK_EXTRAS:-}" ]; then
    case "$source" in
        *://*|*@*) say "PTK_EXTRAS is ignored for URL sources" ;;
        *) source="$source[$PTK_EXTRAS]" ;;
    esac
fi

say "installing $source"
uv tool install --force --python 3.12 "$source"
uv tool update-shell >/dev/null 2>&1 || true

say "done - open a new terminal, then run: ptk doctor"
