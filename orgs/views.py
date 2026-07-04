from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from .models import AuditEvent, Invite, Membership, Org, record
from .permissions import get_membership_or_404


@login_required
def org_new(request):
    error = None
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            error = "Organization name is required."
        elif not slugify(name):
            error = "Name must contain letters or digits."
        else:
            org = Org.objects.create(name=name, slug=Org.unique_slug(name))
            Membership.objects.create(org=org, user=request.user, role=Membership.ADMIN)
            record(org, request.user.username, "org.created")
            return redirect("org-members", org_slug=org.slug)
    return render(request, "orgs/new.html", {"error": error})


@login_required
def members(request, org_slug):
    membership = get_membership_or_404(request, org_slug)
    org = membership.org
    return render(
        request,
        "orgs/members.html",
        {
            "org": org,
            "membership": membership,
            "is_admin": membership.role == Membership.ADMIN,
            "members": org.memberships.select_related("user").order_by("user__username"),
            "pending_invites": org.invites.filter(accepted_at=None),
        },
    )


def _last_admin(org, target: Membership) -> bool:
    return (
        target.role == Membership.ADMIN
        and org.memberships.filter(role=Membership.ADMIN).count() == 1
    )


@login_required
def invite_new(request, org_slug):
    from billing import entitlements

    membership = get_membership_or_404(request, org_slug, admin=True)
    if request.method == "POST":
        if not entitlements.can_add_member(membership.org):
            messages.error(
                request,
                "The Free plan includes 2 members. Upgrade to Team to invite more.",
            )
            return redirect("org-members", org_slug=org_slug)
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", Membership.MEMBER)
        if role not in (Membership.ADMIN, Membership.MEMBER):
            role = Membership.MEMBER
        if email:
            invite = Invite.objects.create(
                org=membership.org, email=email, role=role, created_by=request.user
            )
            record(membership.org, request.user.username, "invite.created",
                   target=email, role=role)
            messages.success(
                request,
                f"Invite created — send this link to {email}: "
                f"{request.build_absolute_uri(f'/invites/{invite.token}/')}",
            )
        else:
            messages.error(request, "Email is required.")
    return redirect("org-members", org_slug=org_slug)


@login_required
def invite_revoke(request, org_slug, pk):
    membership = get_membership_or_404(request, org_slug, admin=True)
    if request.method == "POST":
        invite = get_object_or_404(
            Invite, org=membership.org, pk=pk, accepted_at=None
        )
        record(membership.org, request.user.username, "invite.revoked",
               target=invite.email)
        invite.delete()
    return redirect("org-members", org_slug=org_slug)


@login_required
def member_role(request, org_slug, pk):
    membership = get_membership_or_404(request, org_slug, admin=True)
    if request.method == "POST":
        target = get_object_or_404(Membership, org=membership.org, pk=pk)
        if _last_admin(membership.org, target):
            messages.error(request, "An org must keep at least one admin.")
        else:
            target.role = (
                Membership.MEMBER
                if target.role == Membership.ADMIN
                else Membership.ADMIN
            )
            target.save(update_fields=["role"])
            record(membership.org, request.user.username, "member.role_changed",
                   target=target.user.username, role=target.role)
    return redirect("org-members", org_slug=org_slug)


@login_required
def member_remove(request, org_slug, pk):
    membership = get_membership_or_404(request, org_slug, admin=True)
    if request.method == "POST":
        target = get_object_or_404(Membership, org=membership.org, pk=pk)
        if _last_admin(membership.org, target):
            messages.error(request, "An org must keep at least one admin.")
        else:
            record(membership.org, request.user.username, "member.removed",
                   target=target.user.username)
            target.delete()
            if target.user == request.user:
                return redirect("dashboard")
    return redirect("org-members", org_slug=org_slug)


@login_required
def invite_accept(request, token):
    from billing import entitlements

    invite = Invite.objects.filter(token=token, accepted_at=None).select_related("org").first()
    if invite is None:
        raise Http404
    already_member_now = Membership.objects.filter(
        org=invite.org, user=request.user
    ).exists()
    if request.method == "POST":
        # Re-check at accept time, server-side: the org may have filled up
        # (or downgraded) since the invite link was created.
        if not already_member_now and not entitlements.can_add_member(invite.org):
            return render(
                request,
                "orgs/invite_accept.html",
                {"invite": invite, "already_member": False, "org_full": True},
                status=403,
            )
        invite.accept(request.user)
        record(invite.org, request.user.username, "member.joined",
               invited_by=invite.created_by.username)
        return redirect("dashboard")
    return render(
        request,
        "orgs/invite_accept.html",
        {
            "invite": invite,
            "already_member": already_member_now,
            "org_full": not already_member_now
            and not entitlements.can_add_member(invite.org),
        },
    )


@login_required
def audit_log(request, org_slug):
    membership = get_membership_or_404(request, org_slug, admin=True)
    page = Paginator(
        AuditEvent.objects.filter(org=membership.org), 50
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "orgs/audit.html",
        {"org": membership.org, "page": page, "events": page.object_list},
    )
