"""Remove the stale shared.user DABContentType record.

User is registered in the resource registry as a SharedResource but should NOT
be registered in ANSIBLE_BASE_RBAC_MODEL_REGISTRY.  The combination previously
caused create_DAB_contenttypes() to create a DABContentType with
service='shared', model='user', app_label='core'.  Gateway's
migrate_service_data imported this record, but gateway has no 'core' app, so
DABContentType.model_class() raised LookupError and caused a 500 on the
role_definitions endpoint.
"""

from django.db import migrations


def remove_shared_user_content_type(apps, schema_editor):
    DABContentType = apps.get_model("dab_rbac", "DABContentType")
    DABContentType.objects.filter(service="shared", model="user").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("dab_rbac", "0004_remote_permissions_additions"),
    ]

    operations = [
        migrations.RunPython(
            remove_shared_user_content_type,
            migrations.RunPython.noop,
        ),
    ]
