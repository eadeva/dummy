"""Build the plan of a job (pure).

Named steps use explicit dependencies. --to selects a prerequisite closure;
--only-step deliberately bypasses prerequisite execution.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .. import expressions
from ..config.model import StepSpec
from ..config.substitution import Scope, SubstitutionError
from ..errors import PtkError
from ..graphs import ancestors
from ..suggest import did_you_mean
from .model import PlannedStep


class PlanError(PtkError):
    pass


@dataclass
class PlanContext:
    symbols: Mapping[str, Any]  # for when:
    scope_for: Callable[[tuple[str, ...]], Scope]  # substitution scope of a step
    passthrough: list[str] = field(default_factory=list)
    args_for: dict[str, list[str]] = field(default_factory=dict)  # step label -> args


def select_steps(
    steps: dict[str, StepSpec], end: str | None, only_step: str | None
) -> set[str]:
    if end and only_step:
        raise PlanError("use --to or --only-step, not both")
    for option, name in (("--to", end), ("--only-step", only_step)):
        if name is not None and name not in steps:
            raise PlanError(
                f"{option}: unknown step {name!r}{did_you_mean(name, steps)} (steps: {', '.join(steps)})"
            )
    if only_step:
        return {only_step}
    return {end, *ancestors(steps)[end]} if end else set(steps)


def plan_job(
    steps: dict[str, StepSpec],
    ctx: PlanContext,
    *,
    end: str | None = None,
    only_step: str | None = None,
) -> list[PlannedStep]:
    selected = select_steps(steps, end, only_step)
    planned = [
        _plan(step, (name,), ctx, None if name in selected else "not selected")
        for name, step in steps.items()
    ]
    _apply_passthrough(planned, ctx)
    return planned


def _plan(
    step: StepSpec, path: tuple[str, ...], ctx: PlanContext, selection_skip: str | None
) -> PlannedStep:
    label = "/".join(path)
    skip = selection_skip
    if skip is None and step.only_cx and not ctx.symbols.get("ci", False):
        skip = "only_cx: step requires CX/CI"
    if skip is None:
        skip = variant_restriction(step, ctx.symbols.get("variant"))
    if skip is None and step.when:
        try:
            if not expressions.evaluate(step.when, ctx.symbols):
                skip = f"condition is false: {step.when}"
        except expressions.ExpressionError as exc:
            raise PlanError(f"step '{label}': {exc}") from None
    node = PlannedStep(
        path=path, spec=step, skip_reason=skip, secrets=dict(step.secrets)
    )
    if skip is None:
        scope = ctx.scope_for(path)
        try:
            node.run = scope(step.run) if step.run is not None else None
            if isinstance(node.run, list):
                node.run = [_text(v) for v in node.run]
            elif node.run is not None:
                node.run = _text(node.run)
            node.cwd = _text(scope(step.cwd)) if step.cwd else "."
            node.env = {k: _text(scope(v)) for k, v in step.env.items()}
            node.with_ = scope(step.with_)
            node.outputs = resolve_outputs(step.outputs, scope)
        except SubstitutionError as exc:
            raise PlanError(f"step '{label}': {exc}") from None
    return node


def resolve_outputs(paths, scope):
    resolved = [
        _text(path)
        for path in scope(
            [item if isinstance(item, str) else item.path for item in paths]
        )
    ]
    if any(not path.strip() for path in resolved) or len(set(resolved)) != len(
        resolved
    ):
        raise SubstitutionError("outputs must resolve to unique, non-empty paths")
    return resolved


def _text(value: Any) -> str:
    from ..config.substitution import to_text

    return to_text(value)


def _apply_passthrough(planned: list[PlannedStep], ctx: PlanContext) -> None:
    runnable = [
        s
        for top in planned
        for s in top.walk()
        if s.skip_reason is None and s.kind == "run"
    ]
    by_label = {s.label: s for s in runnable}
    for label, args in ctx.args_for.items():
        target = by_label.get(label)
        if target is None:
            raise PlanError(
                f"--args-for: no runnable step '{label}'{did_you_mean(label, by_label)}"
            )
        if not target.spec.passthrough:
            raise PlanError(
                f"--args-for: step '{label}' does not accept extra arguments (passthrough: true)"
            )
        _append(target, args)
    if not ctx.passthrough:
        return
    targets = [
        s for s in runnable if s.spec.passthrough and s.label not in ctx.args_for
    ]
    if not targets:
        raise PlanError(
            "extra arguments after '--' given, but no selected step has 'passthrough: true'"
        )
    if len(targets) > 1:
        raise PlanError(
            "extra arguments after '--' are ambiguous: several steps accept them "
            f'({", ".join(s.label for s in targets)}); use --args-for STEP="..."'
        )
    _append(targets[0], ctx.passthrough)


def _append(step: PlannedStep, args: list[str]) -> None:
    import shlex

    if isinstance(step.run, list):
        step.run = [*step.run, *args]
    elif step.run is not None:
        step.run = " ".join([step.run, *(shlex.quote(a) for a in args)])


def variant_restriction(spec, variant):
    name = variant or "default"
    if spec.only_variants and name not in spec.only_variants:
        return f"variant {name!r} is not in only_variants"
    if name in spec.omit_variants:
        return f"variant {name!r} is in omit_variants"
    return None
