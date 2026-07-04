"""Create Preview rows from an uploaded JSONL stream.

Single code path for API ingest and dev seeding, so seeded data is exactly
what a real upload would produce.
"""
from orgs.models import record
from projects.models import Project

from .models import Preview
from .reportjson import parse_jsonl, snapshot


class NoEventsError(ValueError):
    pass


def store_preview(
    project: Project,
    text: str,
    *,
    repo: str = "",
    branch: str = "",
    commit: str = "",
    pr_number=None,
    actor: str = "",
) -> Preview:
    report = parse_jsonl(text)
    if not report.hosts and not report.no_hosts_matched:
        raise NoEventsError("no playcheck events found")
    parsed = snapshot(report)
    summary = parsed["summary"]
    preview = Preview.objects.create(
        project=project,
        repo=repo[:200],
        branch=branch[:200],
        commit=commit[:64],
        pr_number=pr_number,
        actor=actor[:100],
        raw_events=text,
        parsed=parsed,
        hosts_total=summary["hosts_total"],
        hosts_changed=summary["hosts_changed"],
        tasks_changed=summary["tasks_changed"],
        not_previewed=summary["not_previewable"],
        failed=summary["failed"],
    )
    record(
        project.org,
        actor or f"token {project.token_prefix}…",
        "preview.uploaded",
        target=project.slug,
        preview_id=preview.pk,
        branch=branch,
        commit=commit[:12],
    )
    return preview
