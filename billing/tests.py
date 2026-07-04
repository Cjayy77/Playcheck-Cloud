"""Entitlement gates and Creem webhook tests.

Every gate is exercised through the HTTP layer to prove enforcement is
server-side, not cosmetic.
"""
import hashlib
import hmac
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orgs.models import AuditEvent, Invite, Membership, Org
from previews.services import store_preview
from previews.tests import FIXTURE_TEXT
from projects.models import Project

from .models import Subscription
from .views import apply_event


def make_org(team=False):
    admin = User.objects.create_user("admin-user")
    org = Org.objects.create(name="acme", slug="acme")
    Membership.objects.create(org=org, user=admin, role=Membership.ADMIN)
    project = Project(org=org, name="infra")
    project.issue_token()
    project.save()
    if team:
        Subscription.objects.create(org=org, status="active")
    return admin, org, project


class ProjectLimitTests(TestCase):
    def test_free_org_blocked_at_one_project(self):
        admin, org, _ = make_org()
        self.client.force_login(admin)
        response = self.client.post(
            reverse("project-new", args=[org.slug]), {"name": "second"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Free plan limit", status_code=403)
        self.assertEqual(org.projects.count(), 1)

    def test_team_org_unlimited_projects(self):
        admin, org, _ = make_org(team=True)
        self.client.force_login(admin)
        response = self.client.post(
            reverse("project-new", args=[org.slug]), {"name": "second"}
        )
        self.assertEqual(response.status_code, 200)  # token_once page
        self.assertEqual(org.projects.count(), 2)


class MemberLimitTests(TestCase):
    def setUp(self):
        self.admin, self.org, _ = make_org()
        self.second = User.objects.create_user("second")
        Membership.objects.create(org=self.org, user=self.second)

    def test_free_org_cannot_invite_third_member(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("org-invite-new", args=[self.org.slug]),
            {"email": "third@example.com", "role": "member"},
        )
        self.assertFalse(Invite.objects.filter(org=self.org).exists())

    def test_accept_rechecks_limit_server_side(self):
        # Invite created while there was room...
        Membership.objects.filter(org=self.org, user=self.second).delete()
        invite = Invite.objects.create(
            org=self.org, email="x@example.com", created_by=self.admin
        )
        # ...but the org filled up before it was accepted.
        Membership.objects.create(org=self.org, user=self.second)
        joiner = User.objects.create_user("joiner")
        self.client.force_login(joiner)
        response = self.client.post(reverse("invite-accept", args=[invite.token]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Membership.objects.filter(org=self.org, user=joiner).exists()
        )

    def test_team_org_can_invite_more(self):
        Subscription.objects.create(org=self.org, status="active")
        self.client.force_login(self.admin)
        self.client.post(
            reverse("org-invite-new", args=[self.org.slug]),
            {"email": "third@example.com", "role": "member"},
        )
        self.assertTrue(Invite.objects.filter(org=self.org).exists())


class HistoryLimitTests(TestCase):
    def setUp(self):
        self.admin, self.org, self.project = make_org()
        self.old = store_preview(self.project, FIXTURE_TEXT, branch="main")
        Preview = type(self.old)
        Preview.objects.filter(pk=self.old.pk).update(
            created_at=timezone.now() - timedelta(days=20)
        )
        self.recent = store_preview(self.project, FIXTURE_TEXT, branch="main")
        self.client.force_login(self.admin)

    def list_url(self):
        return reverse("preview-list", args=[self.org.slug, self.project.slug])

    def detail_url(self, preview):
        return reverse(
            "preview-detail", args=[self.org.slug, self.project.slug, preview.pk]
        )

    def test_free_org_old_previews_hidden_and_blocked(self):
        response = self.client.get(self.list_url())
        self.assertContains(response, "1 older preview hidden")
        response = self.client.get(self.detail_url(self.old))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "NOT PREVIEWED", status_code=403)
        # Recent previews unaffected.
        self.assertEqual(self.client.get(self.detail_url(self.recent)).status_code, 200)

    def test_team_org_sees_full_history(self):
        Subscription.objects.create(org=self.org, status="active")
        self.assertEqual(self.client.get(self.detail_url(self.old)).status_code, 200)
        self.assertNotContains(self.client.get(self.list_url()), "older preview")


class WebhookTests(TestCase):
    def setUp(self):
        self.admin, self.org, _ = make_org()

    def test_checkout_completed_upgrades_org(self):
        handled = apply_event(
            {
                "eventType": "checkout.completed",
                "object": {
                    "metadata": {"org_id": self.org.pk},
                    "customer": {"id": "cust_123"},
                    "subscription": {"id": "sub_456", "status": "active"},
                },
            }
        )
        self.assertTrue(handled)
        subscription = Subscription.objects.get(org=self.org)
        self.assertTrue(subscription.is_team)
        self.assertEqual(subscription.creem_customer_id, "cust_123")
        self.assertEqual(subscription.creem_subscription_id, "sub_456")
        self.assertTrue(
            AuditEvent.objects.filter(org=self.org, action="billing.upgraded").exists()
        )

    def test_subscription_canceled_downgrades_org(self):
        Subscription.objects.create(
            org=self.org, status="active", creem_subscription_id="sub_456"
        )
        apply_event(
            {
                "eventType": "subscription.canceled",
                "object": {"id": "sub_456", "status": "canceled"},
            }
        )
        subscription = Subscription.objects.get(org=self.org)
        self.assertFalse(subscription.is_team)
        self.assertTrue(
            AuditEvent.objects.filter(
                org=self.org, action="billing.downgraded"
            ).exists()
        )

    @override_settings(CREEM_WEBHOOK_SECRET="whsec_test")
    def test_webhook_view_verifies_signature(self):
        payload = json.dumps(
            {
                "eventType": "checkout.completed",
                "object": {
                    "metadata": {"org_id": self.org.pk},
                    "customer": {"id": "cust_1"},
                    "subscription": {"id": "sub_1", "status": "active"},
                },
            }
        ).encode()
        url = reverse("creem-webhook")

        bad = self.client.post(
            url, payload, content_type="application/json",
            HTTP_CREEM_SIGNATURE="nope",
        )
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(Subscription.objects.filter(org=self.org).exists())

        signature = hmac.new(b"whsec_test", payload, hashlib.sha256).hexdigest()
        good = self.client.post(
            url, payload, content_type="application/json",
            HTTP_CREEM_SIGNATURE=signature,
        )
        self.assertEqual(good.status_code, 200)
        self.assertTrue(Subscription.objects.get(org=self.org).is_team)

    @override_settings(CREEM_WEBHOOK_SECRET="", DEBUG=False)
    def test_unconfigured_secret_rejected_in_production(self):
        response = self.client.post(
            reverse("creem-webhook"), b"{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


class DocsPageTests(TestCase):
    def test_docs_page_public(self):
        response = self.client.get(reverse("docs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/api/v1/previews")
        self.assertContains(response, "upload-url")
        self.assertContains(response, "--save-events")
