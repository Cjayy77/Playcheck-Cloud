"""Org access helpers. 404 (not 403) for non-members so org existence and
names never leak across tenants."""
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Membership, Org


def get_membership_or_404(request, org_slug: str, *, admin: bool = False) -> Membership:
    membership = (
        Membership.objects.filter(user=request.user, org__slug=org_slug)
        .select_related("org")
        .first()
    )
    if membership is None:
        raise Http404
    if admin and membership.role != Membership.ADMIN:
        raise Http404
    return membership


def user_orgs(user):
    return Org.objects.filter(memberships__user=user)
