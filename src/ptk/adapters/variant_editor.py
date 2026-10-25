"""Optional GUI plugin discovery and exclusive export."""

from importlib.metadata import entry_points
from pathlib import Path

from ..application.use_cases.variant_editor import VariantEditorSession
from ..domain.errors import PtkError


def save_edit(session: VariantEditorSession, text: str, output: Path) -> None:
    rendered = session.render(text)
    try:
        # Exclusive creation also rejects symlinks and protects source files.
        with output.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    except OSError as exc:
        raise PtkError(f"cannot export {output}: {exc}") from None


def launch_editor(session: VariantEditorSession, output: Path, plugin: str) -> None:
    if output.exists() or output.is_symlink():
        raise PtkError(f"refusing to overwrite {output}")
    if plugin == "tkinter":
        from ..drivers.gui.variants import open_editor
    else:
        matches = list(entry_points(group="ptk.variant_gui", name=plugin))
        if len(matches) != 1:
            raise PtkError(f"variant GUI plugin '{plugin}' is missing or ambiguous")
        try:
            open_editor = matches[0].load()
        except (ImportError, AttributeError) as exc:
            raise PtkError(
                f"cannot load variant GUI plugin '{plugin}': {exc}"
            ) from None
    if not callable(open_editor):
        raise PtkError(f"variant GUI plugin '{plugin}' is not callable")
    open_editor(session, output)
