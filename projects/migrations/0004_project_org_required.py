from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0003_move_projects_to_personal_orgs"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="project",
            name="unique_owner_slug",
        ),
        migrations.RemoveField(
            model_name="project",
            name="owner",
        ),
        migrations.AlterField(
            model_name="project",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="projects",
                to="orgs.org",
            ),
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(fields=("org", "slug"), name="unique_org_slug"),
        ),
    ]
