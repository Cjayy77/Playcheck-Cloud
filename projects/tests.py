from django.contrib.auth.models import User
from django.test import TestCase

from orgs.models import Membership, Org

from .models import Project, hash_token


def org_with_admin(username="alice", org_name="alice-co"):
    user = User.objects.create_user(username)
    org = Org.objects.create(name=org_name, slug=Org.unique_slug(org_name))
    Membership.objects.create(org=org, user=user, role=Membership.ADMIN)
    return user, org


class TokenTests(TestCase):
    def setUp(self):
        self.user, self.org = org_with_admin()
        self.project = Project(org=self.org, name="infra")
        self.token = self.project.issue_token()
        self.project.save()

    def test_plaintext_token_never_stored(self):
        self.assertTrue(self.token.startswith("pck_"))
        self.assertNotEqual(self.project.token_hash, self.token)
        self.assertEqual(self.project.token_hash, hash_token(self.token))
        # Nothing longer than the display prefix is kept in plaintext.
        self.assertNotIn(self.token[12:], self.project.token_prefix)

    def test_authenticate_token(self):
        self.assertEqual(Project.authenticate_token(self.token), self.project)
        self.assertIsNone(Project.authenticate_token("pck_wrong"))
        self.assertIsNone(Project.authenticate_token(""))
        self.assertIsNone(Project.authenticate_token("not-a-playcheck-token"))

    def test_rotate_invalidates_old_token(self):
        new_token = self.project.issue_token()
        self.project.save()
        self.assertIsNone(Project.authenticate_token(self.token))
        self.assertEqual(Project.authenticate_token(new_token), self.project)

    def test_dashboard_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_dashboard_creates_personal_org(self):
        user = User.objects.create_user("newbie")
        self.client.force_login(user)
        self.client.get("/")
        self.assertTrue(
            Membership.objects.filter(user=user, org__is_personal=True).exists()
        )
