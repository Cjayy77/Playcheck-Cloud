from django.contrib import admin

from .models import AuditEvent, Invite, Membership, Org


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_personal", "created_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("org", "user", "role", "created_at")


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("org", "email", "role", "created_by", "accepted_at")
    exclude = ("token",)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("org", "actor", "action", "target", "created_at")
    list_filter = ("action",)
