from django.db import models

from orgs.models import Org

# Creem subscription statuses that entitle the org to the Team tier.
TEAM_STATUSES = ("active", "trialing")


class Subscription(models.Model):
    """One row per org that has ever touched Creem. Absence of a row (or a
    non-team status) means the Free tier. Webhooks are the only writer of
    status fields — never set them from user-facing views."""

    org = models.OneToOneField(Org, on_delete=models.CASCADE, related_name="subscription")
    creem_customer_id = models.CharField(max_length=100, blank=True)
    creem_subscription_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=30, blank=True)  # Creem status verbatim
    current_period_end = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.org.slug}: {self.status or 'free'}"

    @property
    def is_team(self) -> bool:
        return self.status in TEAM_STATUSES
