from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render

from orgs.models import get_or_create_personal_org, record
from orgs.permissions import get_membership_or_404, user_orgs

from .models import Project


@login_required
def dashboard(request):
    # First visit after signup: make sure the personal org exists.
    get_or_create_personal_org(request.user)
    orgs = (
        user_orgs(request.user)
        .prefetch_related("projects")
        .annotate(project_count=Count("projects"))
    )
    org_sections = []
    for org in orgs:
        projects = org.projects.annotate(
            preview_count=Count("previews"), last_upload=Max("previews__created_at")
        )
        org_sections.append({"org": org, "projects": projects})
    return render(request, "dashboard.html", {"org_sections": org_sections})


@login_required
def project_new(request, org_slug):
    from billing import entitlements

    membership = get_membership_or_404(request, org_slug, admin=True)
    org = membership.org
    if not entitlements.can_add_project(org):
        # Server-side gate — Free tier allows one project per org.
        return render(
            request,
            "billing/limit_reached.html",
            {
                "org": org,
                "message": "The Free plan includes one project per organization.",
            },
            status=403,
        )
    error = None
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            error = "Project name is required."
        elif Project.objects.filter(org=org, name=name).exists():
            error = "This org already has a project with that name."
        else:
            project = Project(org=org, name=name)
            token = project.issue_token()
            project.save()
            record(org, request.user.username, "project.created", target=project.slug)
            # Shown exactly once; only the hash is stored.
            return render(
                request, "projects/token_once.html", {"org": org, "project": project, "token": token}
            )
    return render(request, "projects/new.html", {"org": org, "error": error})


@login_required
def project_settings(request, org_slug, project_slug):
    membership = get_membership_or_404(request, org_slug)
    project = get_object_or_404(Project, org=membership.org, slug=project_slug)
    return render(
        request,
        "projects/settings.html",
        {"org": membership.org, "project": project, "is_admin": membership.role == "admin"},
    )


@login_required
def token_rotate(request, org_slug, project_slug):
    membership = get_membership_or_404(request, org_slug, admin=True)
    project = get_object_or_404(Project, org=membership.org, slug=project_slug)
    if request.method != "POST":
        return redirect("project-settings", org_slug=org_slug, project_slug=project_slug)
    token = project.issue_token()
    project.save()
    record(membership.org, request.user.username, "token.rotated", target=project.slug)
    return render(
        request,
        "projects/token_once.html",
        {"org": membership.org, "project": project, "token": token},
    )
