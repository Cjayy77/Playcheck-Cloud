from orgs.permissions import user_orgs


def sidebar_projects(request):
    if not request.user.is_authenticated:
        return {"sidebar_orgs": []}
    return {"sidebar_orgs": user_orgs(request.user).prefetch_related("projects")}
