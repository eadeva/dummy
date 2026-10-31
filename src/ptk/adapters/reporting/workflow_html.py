"""Workflow report built from the execution result and immutable child snapshots."""

from ...domain.graphs import describe_graph
from .. import graph_html
from . import diagnostics, html, needs_html, ui
from .diagnostics import Diagnostic
from .ui import anchor, e, fields, link


def render(result, target, *, owner_variant, children, context):
    graph = describe_graph({job.id: job for job in result.jobs})
    entries, items, configuration, evidence = [], [], [], []
    for node, job in zip(graph["nodes"], result.jobs, strict=True):
        report = children.get(job.id)
        identity = f"[{job.variant or 'default'}][{job.repo + ':' if job.repo else ''}{job.job}]"
        destination = anchor("job", job.id)
        message = job.message or (
            "Child report contains findings or could not be written"
            if job.report_errors
            else ""
        )
        links = " · ".join(link(path, target) for path in job.reports)
        detail = fields(
            {
                "Invocation": job.id,
                "Needs": ", ".join(job.needs) or "None",
                "Variant": job.variant or "default",
                "Run": job.run_id or "Not started",
            }
        )
        if message:
            detail += f"<p>{e(message)}</p>"
        if links:
            detail += f"<p>{links}</p>"
            evidence.append(f"<li>{e(identity)} · {links}</li>")
        if report:
            child_items = diagnostics.collect(
                report, identity, target, scope=job.id, allowed=job.allowed_failure
            )
            items.extend(child_items)
            steps = html.step_entries(report, target, scope=job.id)
            for step in steps:
                detail += f'<details class="execution-item" id="{e(step["target"])}"><summary><span class="entity step">{e(step["label"])}</span> {ui.badge(step["status"], step.get("allowed"))}</summary><div class="item-detail">{step["detail"]}<button type="button" data-show-graph="{e(step["target"])}">Show in graph</button></div></details>'
            node["children"] = html.recorded_graph(report, scope=job.id)
            configuration.append(
                '<details><summary><span class="entity job">'
                + e(identity)
                + "</span> · "
                + e(html.version(report))
                + '</summary><div class="item-detail">'
                + html.configuration(report)
                + "</div></details>"
            )
            if report.coverage:
                evidence.append(
                    "<li>" + e(identity) + html.evidence(report, target) + "</li>"
                )
        if job.status == "failed" and not any(
            item.source == "execution" for item in items if item.owner == identity
        ):
            items.append(
                Diagnostic(
                    identity,
                    "",
                    "execution",
                    "error",
                    message or "Job failed before step results were recorded",
                    allowed=job.allowed_failure,
                    target=destination,
                )
            )
        if job.report_errors and not any(
            item.owner == identity and item.severity == "error" for item in items
        ):
            items.append(
                Diagnostic(
                    identity,
                    "",
                    "report",
                    "error",
                    "Child report contains errors or could not be written",
                    target=destination,
                )
            )
        entries.append(
            {
                "target": destination,
                "label": f"{job.id} · {job.repo + ':' if job.repo else ''}{job.job}",
                "owner": identity,
                "kind": "job",
                "status": job.status.value,
                "duration": job.duration,
                "start": job.start,
                "allowed": job.allowed_failure,
                "detail": detail,
            }
        )
        node.update(
            label=f"{job.repo}:{job.job}" if job.repo else job.job,
            variant=job.variant or "default",
            status=job.status.value,
            duration=job.duration,
            allowed_failure=job.allowed_failure,
            message=message,
            kind="job",
            target=destination,
        )
    scope = "workspace" if context.get("workspace") else owner_variant or "default"
    reports = [children[job.id] for job in result.jobs if job.id in children]
    transcript = target / "workflow.log"
    evidence_html = (
        (
            "<p>" + link(transcript, target, "Workflow transcript") + "</p>"
            if transcript.is_file()
            else ""
        )
        + '<ul class="evidence-links">'
        + "".join(evidence)
        + "</ul>"
    )
    return ui.page(
        title=f"Workflow - {result.name}",
        kind="workflow",
        name=result.name,
        status=result.status.value,
        metadata={
            "Owner": f"[{scope}][{result.name}]",
            "Started": context.get("started_at", "Not recorded"),
            "Duration": f"{result.duration:.2f}s",
            "Run": context.get("run_id", target.name),
        },
        overview=html.overview(entries, reports, items, entity="Jobs"),
        failures=diagnostics.failures(items),
        execution_html=ui.execution(
            entries,
            "Recorded jobs · select a job for its steps, dependencies and child report.",
        ),
        graph=graph_html.section(graph, f"Workflow {result.name}"),
        timeline_html=ui.timeline(entries, result.duration),
        diagnostics=diagnostics.render(
            items,
            analysis_enabled=any(report.log_analysis_enabled for report in reports),
        ),
        tests=html.tests_section(reports),
        needs=needs_html.section(reports, target),
        evidence=evidence_html or "<p>No report attachments recorded.</p>",
        configuration="".join(configuration)
        or '<p class="meta">No child project metadata recorded.</p>',
    ), graph
