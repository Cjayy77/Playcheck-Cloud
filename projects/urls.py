from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("o/<slug:org_slug>/projects/new/", views.project_new, name="project-new"),
    path(
        "o/<slug:org_slug>/p/<slug:project_slug>/settings/",
        views.project_settings,
        name="project-settings",
    ),
    path(
        "o/<slug:org_slug>/p/<slug:project_slug>/token/rotate/",
        views.token_rotate,
        name="token-rotate",
    ),
]
