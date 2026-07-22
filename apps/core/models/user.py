from ansible_base.lib.abstract_models.user import AbstractDABUser


class User(AbstractDABUser):
    """
    Custom User model extending DAB's AbstractDABUser.

    This model can be extended with additional fields as needed.
    """

    encrypted_fields = ["password"]

    @property
    def is_platform_auditor(self) -> bool:
        """True if the user holds the Platform Auditor global RBAC role.

        The gateway conveys auditor status via the JWT global_roles claim (not
        user_data), so this is an RBAC lookup rather than a stored flag.
        DAB's has_super_permission checks getattr(user, bypass_flag) for the
        'view' action; this property makes that work for auditors.
        """
        from ansible_base.rbac.models import RoleDefinition

        return RoleDefinition.objects.filter(
            name="Platform Auditor",
            user_assignments__user=self.pk,
            content_type=None,
        ).exists()

    def related_fields(self, request):
        return {}

    def get_summary_fields(self):
        return {}
