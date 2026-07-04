"""Turn a playcheck RunReport into a JSON snapshot the templates can render.

All *classification* comes from the `playcheck` package — the canonical
parser is the single source of truth for what "NOT PREVIEWED" means. This
module only reshapes the parsed report for storage and HTML rendering. We
also reuse playcheck's diff-line builder (`render._diff_lines`) rather than
reimplementing unified-diff assembly; the version pin in requirements.txt
guards the private import.
"""
from typing import Any, Dict, List

from playcheck.model import Category, HostGroup, RunReport, group_identical_hosts
from playcheck.parse import parse_events
from playcheck.render import _diff_lines

SNAPSHOT_VERSION = 2

_HIDDEN_REASON = {
    True: "diff censored (no_log)",
    False: "diff hidden by task setting (diff: false)",
}


def _entry_header(entry: Dict[str, Any]) -> str:
    return str(entry.get("after_header") or entry.get("before_header") or "diff")


def _diff_entries(result) -> List[Dict[str, Any]]:
    """One block per ansible diff entry: filename header + gutter-typed lines.

    The `---`/`+++` file lines duplicate the header bar, so they are dropped;
    add/del/context markers move to a `marker` field for the gutter column.
    """
    entries: List[Dict[str, Any]] = []
    for entry in result.diff:
        lines: List[Dict[str, str]] = []
        for line in _diff_lines(entry):
            if line.startswith(("+++", "---")):
                continue
            if line.startswith("@@"):
                lines.append({"kind": "hunk", "marker": "@@", "text": line})
            elif line.startswith("+"):
                lines.append({"kind": "add", "marker": "+", "text": line[1:]})
            elif line.startswith("-"):
                lines.append({"kind": "del", "marker": "-", "text": line[1:]})
            else:
                text = line[1:] if line.startswith(" ") else line
                lines.append({"kind": "ctx", "marker": "", "text": text})
        if lines:
            entries.append({"header": _entry_header(entry), "lines": lines})
    return entries


def _task_dict(result) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "task": result.task,
        "action": result.action,
        "short_action": result.action.rsplit(".", 1)[-1],
        "play": result.play,
        "category": result.category.value,
        "msg": result.msg,
        "ignore_errors": result.ignore_errors,
    }
    if result.category is Category.CHANGED:
        d["diffs"] = _diff_entries(result)
    elif result.category is Category.CHANGED_DIFF_HIDDEN:
        d["hidden_reason"] = _HIDDEN_REASON[result.censored]
    elif result.category is Category.NOT_PREVIEWABLE:
        d["note"] = result.msg or "module does not support check mode"
    return d


_INTERESTING = (
    Category.CHANGED,
    Category.CHANGED_DIFF_HIDDEN,
    Category.NOT_PREVIEWABLE,
    Category.RAN_FOR_REAL,
    Category.FAILED,
    Category.UNREACHABLE,
)


def _group_dict(group: HostGroup) -> Dict[str, Any]:
    h = group.report
    return {
        "hosts": group.hosts,
        "label": group.label(),
        "changes": h.count(Category.CHANGED, Category.CHANGED_DIFF_HIDDEN),
        "not_previewable": h.count(Category.NOT_PREVIEWABLE),
        "failed": h.count(Category.FAILED),
        "unreachable": h.count(Category.UNREACHABLE),
        "ran_for_real": h.count(Category.RAN_FOR_REAL),
        "quiet_ok": h.count(Category.OK),
        "quiet_skipped": h.count(Category.SKIPPED),
        "tasks": [_task_dict(r) for r in h.results if r.category in _INTERESTING],
    }


def snapshot(report: RunReport) -> Dict[str, Any]:
    hosts_changed = sum(
        1
        for h in report.hosts.values()
        if h.count(Category.CHANGED, Category.CHANGED_DIFF_HIDDEN)
    )
    return {
        "version": SNAPSHOT_VERSION,
        "plays": report.plays,
        "no_hosts_matched": report.no_hosts_matched,
        "unparsed_lines": len(report.unparsed_lines),
        "summary": {
            "hosts_total": len(report.hosts),
            "hosts_changed": hosts_changed,
            "tasks_changed": report.count(Category.CHANGED, Category.CHANGED_DIFF_HIDDEN),
            "diffs_hidden": report.count(Category.CHANGED_DIFF_HIDDEN),
            "not_previewable": report.count(Category.NOT_PREVIEWABLE),
            "ran_for_real": report.count(Category.RAN_FOR_REAL),
            "failed": report.count(Category.FAILED, Category.UNREACHABLE),
        },
        "groups": [_group_dict(g) for g in group_identical_hosts(report.hosts)],
    }


def parse_jsonl(text: str) -> RunReport:
    return parse_events(text.splitlines())
