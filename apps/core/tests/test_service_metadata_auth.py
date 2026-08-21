"""Tests for the ServiceMetadataView authentication patch.

The gateway's populate_service_id self-heal probes GET
/api/v1/service-index/metadata/ to resolve a service whose
ServiceCluster.service_id is still NULL after a 2.6->2.7 upgrade. The default
RBAC auth class re-calls the gateway (jwt_claims) during authentication, which
503s while service_id is unresolved, so the probe 403s and service_id stays
NULL forever. CoreConfig._restrict_dab_view_permissions patches this one view
to authenticate without the RBAC claims fetch. These tests guard that wiring.
"""

from ansible_base.jwt_consumer.common.auth import JWTAuthentication
from ansible_base.resource_registry.views import ServiceMetadataView

from apps.core.apps import CoreConfig
from apps.core.authentication import ServiceJWTAuthenticationNoRBAC


class TestServiceJWTAuthenticationNoRBAC:
    """The no-RBAC auth class keeps JWT validation but skips the claims fetch."""

    def test_is_jwt_authentication_subclass(self):
        """It must still be a real DAB JWT authenticator (auth is not weakened)."""
        assert issubclass(ServiceJWTAuthenticationNoRBAC, JWTAuthentication)

    def test_rbac_permissions_disabled(self):
        """use_rbac_permissions=False is what avoids the recursive gateway call."""
        assert ServiceJWTAuthenticationNoRBAC.use_rbac_permissions is False


class TestServiceMetadataViewPatch:
    """ServiceMetadataView must be patched to the no-RBAC auth class."""

    def test_metadata_view_uses_no_rbac_auth(self):
        """The AppConfig patch applied at startup must be in effect."""
        assert ServiceMetadataView.authentication_classes == [ServiceJWTAuthenticationNoRBAC]

    def test_patch_is_idempotent(self):
        """Re-running the patch (e.g. app reload) leaves the same wiring."""
        CoreConfig._restrict_dab_view_permissions()
        assert ServiceMetadataView.authentication_classes == [ServiceJWTAuthenticationNoRBAC]
