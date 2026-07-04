from django.urls import path

from . import views

urlpatterns = [
    path("orgs/new/", views.org_new, name="org-new"),
    path("o/<slug:org_slug>/members/", views.members, name="org-members"),
    path("o/<slug:org_slug>/members/invite/", views.invite_new, name="org-invite-new"),
    path(
        "o/<slug:org_slug>/invites/<int:pk>/revoke/",
        views.invite_revoke,
        name="org-invite-revoke",
    ),
    path(
        "o/<slug:org_slug>/members/<int:pk>/role/",
        views.member_role,
        name="org-member-role",
    ),
    path(
        "o/<slug:org_slug>/members/<int:pk>/remove/",
        views.member_remove,
        name="org-member-remove",
    ),
    path("o/<slug:org_slug>/audit/", views.audit_log, name="org-audit"),
    path("invites/<str:token>/", views.invite_accept, name="invite-accept"),
]
