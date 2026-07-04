import hashlib
import secrets

from django.db import models
from django.utils.text import slugify

TOKEN_PREFIX_LEN = 12  # "pck_" + 8 chars, enough to index without exposing the token


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Project(models.Model):
    """A repo/playbook whose previews land here.

    Tenancy: every project belongs to an org (personal orgs stand in for
    solo users). Every query that touches previews must go through an org
    the requesting user is a member of.
    """

    org = models.ForeignKey(
        "orgs.Org", on_delete=models.CASCADE, related_name="projects"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    token_prefix = models.CharField(max_length=TOKEN_PREFIX_LEN, db_index=True)
    token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "slug"], name="unique_org_slug"),
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "project"
        super().save(*args, **kwargs)

    def issue_token(self) -> str:
        """Generate a fresh upload token; only the hash is stored. Returns the
        plaintext token exactly once — it cannot be recovered later."""
        token = "pck_" + secrets.token_urlsafe(32)
        self.token_prefix = token[:TOKEN_PREFIX_LEN]
        self.token_hash = hash_token(token)
        return token

    @classmethod
    def authenticate_token(cls, token: str):
        """Constant-time token check; returns the Project or None."""
        if not token or not token.startswith("pck_"):
            return None
        candidates = cls.objects.filter(token_prefix=token[:TOKEN_PREFIX_LEN])
        digest = hash_token(token)
        for project in candidates:
            if secrets.compare_digest(project.token_hash, digest):
                return project
        return None
