from django.urls import path

from . import views

urlpatterns = [
    path(
        "o/<slug:org_slug>/p/<slug:project_slug>/",
        views.preview_list,
        name="preview-list",
    ),
    path(
        "o/<slug:org_slug>/p/<slug:project_slug>/previews/<int:pk>/",
        views.preview_detail,
        name="preview-detail",
    ),
]
