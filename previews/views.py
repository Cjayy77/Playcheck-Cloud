from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from orgs.models import record
from orgs.permissions import get_membership_or_404
from projects.models import Project

from .models import Preview

PAGE_SIZE = 25


def _member_project(request, org_slug, project_slug):
    """Every project lookup goes through the requester's membership —
    tenant isolation depends on this being the only path."""
    membership = get_membership_or_404(request, org_slug)
    project = get_object_or_404(Project, org=membership.org, slug=project_slug)
    return membership, project


@login_required
def preview_list(request, org_slug, project_slug):
    from billing import entitlements

    membership, project = _member_project(request, org_slug, project_slug)
    previews = project.previews.all()
    branch = request.GET.get("branch", "").strip()
    if branch:
        previews = previews.filter(branch=branch)
    # Free tier: only recent history is visible (enforced here, not in CSS).
    cutoff = entitlements.history_cutoff(membership.org)
    hidden_count = 0
    if cutoff is not None:
        hidden_count = previews.filter(created_at__lt=cutoff).count()
        previews = previews.filter(created_at__gte=cutoff)
    branches = (
        project.previews.exclude(branch="")
        .values_list("branch", flat=True)
        .distinct()
        .order_by("branch")
    )
    page = Paginator(previews, PAGE_SIZE).get_page(request.GET.get("page"))
    template = (
        "previews/_list_rows.html"
        if request.headers.get("HX-Request")
        else "previews/list.html"
    )
    return render(
        request,
        template,
        {
            "org": membership.org,
            "project": project,
            "page": page,
            "previews": page.object_list,
            "branches": branches,
            "branch": branch,
            "hidden_count": hidden_count,
            "is_admin": membership.role == "admin",
        },
    )


@login_required
def preview_detail(request, org_slug, project_slug, pk):
    from billing import entitlements

    membership, project = _member_project(request, org_slug, project_slug)
    preview = get_object_or_404(Preview, project=project, pk=pk)
    cutoff = entitlements.history_cutoff(membership.org)
    if cutoff is not None and preview.created_at < cutoff:
        # Server-side history gate: the payload must not reach the template.
        return render(
            request,
            "billing/limit_reached.html",
            {
                "org": membership.org,
                "message": "This preview is older than the Free plan's "
                "14-day history window.",
            },
            status=403,
        )
    record(
        membership.org,
        request.user.username,
        "preview.viewed",
        target=f"{project.slug}#{preview.pk}",
    )
    return render(
        request,
        "previews/detail.html",
        {
            "org": membership.org,
            "project": project,
            "preview": preview,
            "report": preview.parsed,
        },
    )
