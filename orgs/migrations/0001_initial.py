from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Org",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("is_personal", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("admin", "Admin"), ("member", "Member")], default="member", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("org", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="orgs.org")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Invite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("role", models.CharField(choices=[("admin", "Admin"), ("member", "Member")], default="member", max_length=10)),
                ("token", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("org", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invites", to="orgs.org")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor", models.CharField(max_length=150)),
                ("action", models.CharField(max_length=50)),
                ("target", models.CharField(blank=True, max_length=200)),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("org", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_events", to="orgs.org")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(fields=("org", "user"), name="unique_org_user"),
        ),
    ]
