from django.contrib import admin

from .models import Preview


@admin.register(Preview)
class PreviewAdmin(admin.ModelAdmin):
    list_display = ("project", "repo", "branch", "commit", "actor", "created_at")
    list_filter = ("project",)
