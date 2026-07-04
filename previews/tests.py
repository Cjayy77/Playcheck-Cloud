"""Ingest, rendering, and — critically — cross-tenant isolation tests.

All parsing assertions run against the real captured fixture
(fixtures/jsonl_output.jsonl from the public Playcheck repo), never
hand-invented JSON.
"""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from orgs.models import Membership, Org
from projects.models import Project

from .models import Preview
from .services import store_preview

FIXTURE = Path(settings.BASE_DIR) / "fixtures" / "jsonl_output.jsonl"
FIXTURE_TEXT = FIXTURE.read_text(encoding="utf-8")

INGEST_URL = "/api/v1/previews"


def make_tenant(username, org_name, project_name):
    """A user who admins an org containing one project."""
    user = User.objects.create_user(username)
    org = Org.objects.create(name=org_name, slug=Org.unique_slug(org_name))
    Membership.objects.create(org=org, user=user, role=Membership.ADMIN)
    project = Project(org=org, name=project_name)
    token = project.issue_token()
    project.save()
    return user, org, project, token


class IngestApiTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters must not leak between tests
        self.user, self.org, self.project, self.token = make_tenant(
            "alice", "alice-co", "infra"
        )

    def post(self, body=FIXTURE_TEXT, token=None, query=""):
        headers = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            INGEST_URL + query,
            data=body,
            content_type="application/x-ndjson",
            **headers,
        )

    def test_upload_with_valid_token(self):
        response = self.post(
            token=self.token,
            query="?repo=acme/infra&branch=main&commit=abc123&pr=17&actor=cedric",
        )
        self.assertEqual(response.status_code, 201)
        summary = response.json()["summary"]
        # Ground truth from the canonical playcheck parser on the real fixture.
        self.assertEqual(summary["not_previewable"], 5)
        self.assertEqual(summary["tasks_changed"], 7)
        self.assertEqual(summary["diffs_hidden"], 2)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["ran_for_real"], 1)
        self.assertEqual(summary["hosts_total"], 2)
        self.assertEqual(summary["hosts_changed"], 2)

        preview = Preview.objects.get(pk=response.json()["id"])
        self.assertEqual(preview.project, self.project)
        self.assertEqual(preview.branch, "main")
        self.assertEqual(preview.pr_number, 17)
        self.assertEqual(preview.not_previewed, 5)
        self.assertEqual(preview.raw_events, FIXTURE_TEXT)  # stored verbatim
        self.assertIn(f"/o/{self.org.slug}/p/", response.json()["url"])

    def test_upload_without_token_rejected(self):
        self.assertEqual(self.post().status_code, 401)

    def test_upload_with_wrong_token_rejected(self):
        self.assertEqual(self.post(token="pck_totally-wrong").status_code, 401)
        self.assertEqual(Preview.objects.count(), 0)

    def test_token_scopes_upload_to_its_own_project(self):
        _, _, project_b, token_b = make_tenant("bob", "bob-co", "other-infra")
        response = self.post(token=token_b)
        self.assertEqual(response.status_code, 201)
        preview = Preview.objects.get()
        self.assertEqual(preview.project, project_b)
        self.assertEqual(self.project.previews.count(), 0)

    def test_empty_body_rejected(self):
        self.assertEqual(self.post(body="", token=self.token).status_code, 400)

    def test_non_playcheck_body_rejected(self):
        response = self.post(body="hello\nworld\n", token=self.token)
        self.assertEqual(response.status_code, 422)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(INGEST_URL).status_code, 405)

    @override_settings(INGEST_UPLOADS_PER_MINUTE=3)
    def test_rate_limited(self):
        for _ in range(3):
            self.assertEqual(self.post(token=self.token).status_code, 201)
        self.assertEqual(self.post(token=self.token).status_code, 429)


class CrossTenantIsolationTests(TestCase):
    """User B must never read user A's org data. Existential — keep green."""

    def setUp(self):
        self.user_a, self.org_a, self.project_a, _ = make_tenant(
            "alice", "alice-co", "alice-private-playbooks"
        )
        self.user_b, self.org_b, _, _ = make_tenant("bob", "bob-co", "bob-stuff")
        self.preview_a = store_preview(self.project_a, FIXTURE_TEXT, branch="main")

    def urls_of_a(self):
        args = [self.org_a.slug, self.project_a.slug]
        return [
            reverse("preview-list", args=args),
            reverse("preview-detail", args=args + [self.preview_a.pk]),
            reverse("project-settings", args=args),
            reverse("org-members", args=[self.org_a.slug]),
            reverse("org-audit", args=[self.org_a.slug]),
        ]

    def test_other_user_gets_404_everywhere(self):
        self.client.force_login(self.user_b)
        for url in self.urls_of_a():
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(
            self.client.post(
                reverse("token-rotate", args=[self.org_a.slug, self.project_a.slug])
            ).status_code,
            404,
        )

    def test_dashboard_lists_only_own_orgs(self):
        self.client.force_login(self.user_b)
        response = self.client.get("/")
        self.assertNotContains(response, self.project_a.name)
        self.assertNotContains(response, self.org_a.name)
        self.assertContains(response, "bob-stuff")

    def test_org_member_can_view_teammates_previews(self):
        # Teams: a member of the same org sees its previews...
        member = User.objects.create_user("carol")
        Membership.objects.create(
            org=self.org_a, user=member, role=Membership.MEMBER
        )
        self.client.force_login(member)
        response = self.client.get(
            reverse(
                "preview-detail",
                args=[self.org_a.slug, self.project_a.slug, self.preview_a.pk],
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_owner_can_view_own_preview(self):
        self.client.force_login(self.user_a)
        response = self.client.get(
            reverse(
                "preview-detail",
                args=[self.org_a.slug, self.project_a.slug, self.preview_a.pk],
            )
        )
        self.assertEqual(response.status_code, 200)


class PreviewRenderingTests(TestCase):
    """The honesty guarantee: NOT-PREVIEWED must be loud on the page."""

    def setUp(self):
        self.user, self.org, self.project, _ = make_tenant(
            "alice", "alice-co", "infra"
        )
        self.preview = store_preview(self.project, FIXTURE_TEXT, branch="main")
        self.client.force_login(self.user)

    def detail(self):
        return self.client.get(
            reverse(
                "preview-detail",
                args=[self.org.slug, self.project.slug, self.preview.pk],
            )
        )

    def test_not_previewed_banner_is_rendered(self):
        response = self.detail()
        self.assertContains(response, "5 tasks were NOT simulated")
        self.assertContains(response, "NOT PREVIEWED")

    def test_diff_lines_rendered_including_loop_items(self):
        response = self.detail()
        self.assertContains(response, "server_name example.com;")
        # Both loop items' diffs must appear (aggregated loop task).
        self.assertContains(response, "shared_buffers=256MB")
        self.assertContains(response, "work_mem=16MB")
        # Diff entries carry their filename header bars.
        self.assertContains(response, "/tmp/playcheck-nginx.conf")

    def test_hidden_diffs_and_failures_labelled(self):
        response = self.detail()
        self.assertContains(response, "diff censored (no_log)")
        self.assertContains(response, "diff hidden by task setting (diff: false)")
        self.assertContains(response, "FAILED (ignored)")
        self.assertContains(response, "executed for real: check_mode: false")

    def test_list_page_shows_not_previewed_badge(self):
        response = self.client.get(
            reverse("preview-list", args=[self.org.slug, self.project.slug])
        )
        self.assertContains(response, "5 NOT previewed")
