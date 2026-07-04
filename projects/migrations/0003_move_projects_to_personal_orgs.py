"""Every pre-org project moves into a personal org for its owner, who becomes
that org's admin. Reversible: the reverse copies org projects back to their
sole admin as owner (only safe while orgs are all personal, which is exactly
the state this migration creates)."""
from django.db import migrations
from django.utils.text import slugify


def _unique_org_slug(Org, name):
    base = slugify(name) or "org"
    slug, n = base, 2
    while Org.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def forwards(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Org = apps.get_model("orgs", "Org")
    Membership = apps.get_model("orgs", "Membership")

    for project in Project.objects.select_related("owner").all():
        owner = project.owner
        membership = Membership.objects.filter(
            user=owner, org__is_personal=True
        ).first()
        if membership:
            org = membership.org
        else:
            org = Org.objects.create(
                name=owner.username,
                slug=_unique_org_slug(Org, owner.username),
                is_personal=True,
            )
            Membership.objects.create(org=org, user=owner, role="admin")
        project.org = org
        project.save(update_fields=["org"])


def backwards(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Membership = apps.get_model("orgs", "Membership")

    for project in Project.objects.all():
        admin = (
            Membership.objects.filter(org=project.org, role="admin")
            .select_related("user")
            .first()
        )
        if admin:
            project.owner = admin.user
            project.save(update_fields=["owner"])


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_project_org_nullable"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
