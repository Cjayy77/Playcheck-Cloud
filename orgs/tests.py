"""Roles, invites, and audit-log tests for slice 2."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from projects.models import Project

from .models import AuditEvent, Invite, Membership, Org


def make_org():
    """Team-tier org so free-plan limits don't interfere with role/invite
    mechanics; the limits themselves are covered in billing/tests.py."""
    from billing.models import Subscription

    admin = User.objects.create_user("admin-user")
    member = User.objects.create_user("member-user")
    org = Org.objects.create(name="acme", slug="acme")
    Subscription.objects.create(org=org, status="active")
    Membership.objects.create(org=org, user=admin, role=Membership.ADMIN)
    member_ship = Membership.objects.create(
        org=org, user=member, role=Membership.MEMBER
    )
    project = Project(org=org, name="infra")
    project.issue_token()
    project.save()
    return admin, member, org, project, member_ship


class RoleGateTests(TestCase):
    def setUp(self):
        self.admin, self.member, self.org, self.project, self.membership = make_org()

    def test_member_cannot_do_admin_things(self):
        self.client.force_login(self.member)
        admin_urls_post = [
            reverse("token-rotate", args=[self.org.slug, self.project.slug]),
            reverse("org-invite-new", args=[self.org.slug]),
            reverse("org-member-role", args=[self.org.slug, self.membership.pk]),
            reverse("org-member-remove", args=[self.org.slug, self.membership.pk]),
        ]
        for url in admin_urls_post:
            self.assertEqual(self.client.post(url).status_code, 404, url)
        self.assertEqual(
            self.client.get(reverse("org-audit", args=[self.org.slug])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("project-new", args=[self.org.slug])).status_code,
            404,
        )

    def test_member_can_view_members_and_previews_pages(self):
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(reverse("org-members", args=[self.org.slug])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("preview-list", args=[self.org.slug, self.project.slug])
            ).status_code,
            200,
        )

    def test_admin_can_rotate_and_sees_audit(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("token-rotate", args=[self.org.slug, self.project.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AuditEvent.objects.filter(org=self.org, action="token.rotated").exists()
        )
        self.assertEqual(
            self.client.get(reverse("org-audit", args=[self.org.slug])).status_code,
            200,
        )

    def test_cannot_demote_or_remove_last_admin(self):
        self.client.force_login(self.admin)
        admin_ship = Membership.objects.get(org=self.org, user=self.admin)
        self.client.post(
            reverse("org-member-role", args=[self.org.slug, admin_ship.pk])
        )
        admin_ship.refresh_from_db()
        self.assertEqual(admin_ship.role, Membership.ADMIN)
        self.client.post(
            reverse("org-member-remove", args=[self.org.slug, admin_ship.pk])
        )
        self.assertTrue(
            Membership.objects.filter(org=self.org, user=self.admin).exists()
        )


class InviteTests(TestCase):
    def setUp(self):
        self.admin, self.member, self.org, self.project, _ = make_org()

    def test_invite_flow(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("org-invite-new", args=[self.org.slug]),
            {"email": "new@example.com", "role": "member"},
        )
        invite = Invite.objects.get(org=self.org, email="new@example.com")

        newcomer = User.objects.create_user("newcomer")
        self.client.force_login(newcomer)
        url = reverse("invite-accept", args=[invite.token])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url)
        self.assertTrue(
            Membership.objects.filter(
                org=self.org, user=newcomer, role=Membership.MEMBER
            ).exists()
        )
        # Accepted invites are single-use.
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertTrue(
            AuditEvent.objects.filter(org=self.org, action="member.joined").exists()
        )

    def test_revoked_invite_unusable(self):
        self.client.force_login(self.admin)
        invite = Invite.objects.create(
            org=self.org, email="x@example.com", created_by=self.admin
        )
        self.client.post(reverse("org-invite-revoke", args=[self.org.slug, invite.pk]))
        self.assertFalse(Invite.objects.filter(pk=invite.pk).exists())

    def test_invite_accept_requires_login(self):
        invite = Invite.objects.create(
            org=self.org, email="x@example.com", created_by=self.admin
        )
        response = self.client.get(reverse("invite-accept", args=[invite.token]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])


class AuditTests(TestCase):
    def setUp(self):
        self.admin, self.member, self.org, self.project, _ = make_org()

    def test_upload_and_view_are_audited(self):
        from previews.services import store_preview
        from previews.tests import FIXTURE_TEXT

        preview = store_preview(self.project, FIXTURE_TEXT, actor="ci-bot")
        self.assertTrue(
            AuditEvent.objects.filter(
                org=self.org, action="preview.uploaded", actor="ci-bot"
            ).exists()
        )
        self.client.force_login(self.member)
        self.client.get(
            reverse(
                "preview-detail",
                args=[self.org.slug, self.project.slug, preview.pk],
            )
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                org=self.org, action="preview.viewed", actor="member-user"
            ).exists()
        )

    def test_project_creation_audited(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("project-new", args=[self.org.slug]), {"name": "new-proj"}
        )
        self.assertTrue(
            AuditEvent.objects.filter(org=self.org, action="project.created").exists()
        )
