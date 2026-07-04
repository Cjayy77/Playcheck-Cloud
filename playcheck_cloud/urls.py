from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from previews.api import ingest_preview

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/v1/previews", ingest_preview, name="api-ingest-preview"),
    path("", include("projects.urls")),
    path("", include("previews.urls")),
    path("", include("orgs.urls")),
    path("", include("billing.urls")),
    path("docs/", TemplateView.as_view(template_name="docs.html"), name="docs"),
]
