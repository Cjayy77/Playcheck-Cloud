import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Org(models.Model):
    """The tenant. Every project belongs to an org; every query that touches
    org data must be scoped through a Membership of the requesting user."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    is_personal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @classmethod
    def unique_slug(cls, name: str) -> str:
        base = slugify(name) or "org"
        slug, n = base, 2
        while cls.objects.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug


def get_or_create_personal_org(user) -> Org:
    membership = (
        Membership.objects.filter(user=user, org__is_personal=True)
        .select_related("org")
        .first()
    )
    if membership:
        return membership.org
    org = Org.objects.create(
        name=user.username, slug=Org.unique_slug(user.username), is_personal=True
    )
    Membership.objects.create(org=org, user=user, role=Membership.ADMIN)
    return org


class Membership(models.Model):
    ADMIN = "admin"
    MEMBER = "member"
    ROLE_CHOICES = [(ADMIN, "Admin"), (MEMBER, "Member")]

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "user"], name="unique_org_user"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.org} ({self.role})"


class Invite(models.Model):
    """Link-based invite: admins copy the accept URL to the invitee — no SMTP
    dependency. The email field records who it was meant for."""

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    role = models.CharField(
        max_length=10, choices=Membership.ROLE_CHOICES, default=Membership.MEMBER
    )
    token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_accepted(self):
        return self.accepted_at is not None

    def accept(self, user):
        Membership.objects.get_or_create(
            org=self.org, user=user, defaults={"role": self.role}
        )
        self.accepted_by = user
        self.accepted_at = timezone.now()
        self.save(update_fields=["accepted_by", "accepted_at"])


class AuditEvent(models.Model):
    """Append-only record of uploads, preview views, and settings changes."""

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.CharField(max_length=150)  # username, or "token <prefix…>" for CI
    action = models.CharField(max_length=50)
    target = models.CharField(max_length=200, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.org.slug}] {self.actor} {self.action} {self.target}"


def record(org: Org, actor: str, action: str, target: str = "", **detail) -> None:
    AuditEvent.objects.create(
        org=org, actor=actor[:150], action=action, target=target[:200], detail=detail
    )
