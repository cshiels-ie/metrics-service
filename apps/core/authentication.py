"""Custom authentication classes for the service."""

from ansible_base.jwt_consumer.common.auth import JWTAuthentication


class ServiceJWTAuthentication(JWTAuthentication):
    """JWT Authentication with RBAC permissions enabled."""

    use_rbac_permissions = True


class ServiceJWTAuthenticationNoRBAC(JWTAuthentication):
    """JWT Authentication without the RBAC claims-sync gateway fetch.

    Validates the DAB JWT (user resolution + is_superuser / resource_api_actions
    stamping) but skips process_rbac_permissions, avoiding the recursive
    jwt_claims call back to the gateway. Applied only to ServiceMetadataView so
    the gateway's populate_service_id probe can succeed while
    ServiceCluster.service_id is still NULL on 2.6->2.7 upgraded deployments.
    """

    use_rbac_permissions = False
