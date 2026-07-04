from django.db import models

from projects.models import Project


class Preview(models.Model):
    """One uploaded `ansible-playbook --check --diff` run.

    `raw_events` keeps the JSONL verbatim (reparseable if the snapshot format
    evolves); `parsed` is the render-ready snapshot built at ingest time by
    previews.reportjson using the canonical playcheck parser.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="previews"
    )
    repo = models.CharField(max_length=200, blank=True)
    branch = models.CharField(max_length=200, blank=True)
    commit = models.CharField(max_length=64, blank=True)
    pr_number = models.PositiveIntegerField(null=True, blank=True)
    actor = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    raw_events = models.TextField()
    parsed = models.JSONField()

    # Denormalized for the list page; source of truth is `parsed`.
    hosts_total = models.PositiveIntegerField(default=0)
    hosts_changed = models.PositiveIntegerField(default=0)
    tasks_changed = models.PositiveIntegerField(default=0)
    not_previewed = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} @ {self.commit[:8] or 'unknown'}"

    @property
    def short_commit(self):
        return self.commit[:8]
