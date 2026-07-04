"""Server-side entitlements. Every gate lives here so limits are enforced in
views (never only in templates) and tests can target one module.

Free tier: 1 project, 14-day preview history, 2 members.
Team tier: unlimited.
"""
from datetime import timedelta

from django.utils import timezone

from orgs.models import Org

FREE_MAX_PROJECTS = 1
FREE_MAX_MEMBERS = 2
FREE_HISTORY_DAYS = 14


def is_team(org: Org) -> bool:
    subscription = getattr(org, "subscription", None)
    return bool(subscription and subscription.is_team)


def plan_name(org: Org) -> str:
    return "Team" if is_team(org) else "Free"


def can_add_project(org: Org) -> bool:
    return is_team(org) or org.projects.count() < FREE_MAX_PROJECTS


def can_add_member(org: Org) -> bool:
    return is_team(org) or org.memberships.count() < FREE_MAX_MEMBERS


def history_cutoff(org: Org):
    """Free orgs only see previews newer than this; None means unlimited."""
    if is_team(org):
        return None
    return timezone.now() - timedelta(days=FREE_HISTORY_DAYS)


def usage(org: Org) -> dict:
    return {
        "plan": plan_name(org),
        "is_team": is_team(org),
        "projects": org.projects.count(),
        "members": org.memberships.count(),
        "max_projects": None if is_team(org) else FREE_MAX_PROJECTS,
        "max_members": None if is_team(org) else FREE_MAX_MEMBERS,
        "history_days": None if is_team(org) else FREE_HISTORY_DAYS,
    }
