"""Seed the dev database: demo user, a team org with a second member, and
previews ingested from the real playcheck fixture.

    python manage.py seed_demo

Users: demo/demo12345 (staff — the admin login is the local stand-in for
GitHub OAuth) as acme admin, and teammate/teammate12345 as acme member.
Fixture data is real captured playcheck output, never hand-invented JSON.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from orgs.models import Membership, Org, get_or_create_personal_org
from previews.services import store_preview
from projects.models import Project

FIXTURE = Path(settings.BASE_DIR) / "fixtures" / "jsonl_output.jsonl"


class Command(BaseCommand):
    help = "Seed demo users, an org, and previews from the real playcheck fixture."

    def _user(self, username, password, **extra):
        user, created = User.objects.get_or_create(username=username, defaults=extra)
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f"created user {username} / {password}")
        get_or_create_personal_org(user)
        return user

    def handle(self, *args, **options):
        if not FIXTURE.exists():
            raise CommandError(f"fixture not found: {FIXTURE}")
        text = FIXTURE.read_text(encoding="utf-8")

        demo = self._user("demo", "demo12345", is_staff=True, is_superuser=True)
        teammate = self._user("teammate", "teammate12345")

        org, created = Org.objects.get_or_create(
            slug="acme", defaults={"name": "acme"}
        )
        Membership.objects.get_or_create(
            org=org, user=demo, defaults={"role": Membership.ADMIN}
        )
        Membership.objects.get_or_create(
            org=org, user=teammate, defaults={"role": Membership.MEMBER}
        )

        project, created = Project.objects.get_or_create(
            org=org, slug="infra-playbooks", defaults={"name": "infra-playbooks"}
        )
        if created:
            token = project.issue_token()
            project.save()
            self.stdout.write(f"created project infra-playbooks; upload token: {token}")

        uploads = [
            dict(repo="acme/infra-playbooks", branch="main",
                 commit="9f3c2a17d4e8b6a0c5f1e2d3a4b5c6d7e8f90102", actor="cedric"),
            dict(repo="acme/infra-playbooks", branch="feature/nginx-tuning",
                 commit="1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d", pr_number=17,
                 actor="cedric"),
        ]
        for meta in uploads:
            preview = store_preview(project, text, **meta)
            self.stdout.write(
                f"preview #{preview.id}: {meta['branch']} — "
                f"{preview.tasks_changed} changes, {preview.not_previewed} not previewed"
            )
        self.stdout.write(self.style.SUCCESS("seeded."))
