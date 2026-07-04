"""Rebuild every Preview's parsed snapshot from its verbatim raw_events.

Run after upgrading the snapshot format or the playcheck package:

    python manage.py reparse_previews
"""
from django.core.management.base import BaseCommand

from previews.models import Preview
from previews.reportjson import SNAPSHOT_VERSION, parse_jsonl, snapshot


class Command(BaseCommand):
    help = "Re-parse all stored previews with the current playcheck parser."

    def handle(self, *args, **options):
        updated = 0
        for preview in Preview.objects.all().iterator():
            parsed = snapshot(parse_jsonl(preview.raw_events))
            summary = parsed["summary"]
            preview.parsed = parsed
            preview.hosts_total = summary["hosts_total"]
            preview.hosts_changed = summary["hosts_changed"]
            preview.tasks_changed = summary["tasks_changed"]
            preview.not_previewed = summary["not_previewable"]
            preview.failed = summary["failed"]
            preview.save(
                update_fields=[
                    "parsed", "hosts_total", "hosts_changed",
                    "tasks_changed", "not_previewed", "failed",
                ]
            )
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(f"reparsed {updated} previews to snapshot v{SNAPSHOT_VERSION}")
        )
