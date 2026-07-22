"""Resource Registry configuration for DAB."""

from ansible_base.resource_registry.registry import (
    ParentResource,
    ResourceConfig,
    ServiceAPIConfig,
    SharedResource,
)
from ansible_base.resource_registry.shared_types import OrganizationType, TeamType, UserType

from apps.core.models import Organization, Team, User


class APIConfig(ServiceAPIConfig):
    """API configuration for the resource registry."""

    service_type = "metrics"


RESOURCE_LIST = [
    ResourceConfig(
        Organization,
        shared_resource=SharedResource(
            serializer=OrganizationType,
            is_provider=False,
        ),
    ),
    ResourceConfig(
        Team,
        shared_resource=SharedResource(
            serializer=TeamType,
            is_provider=False,
        ),
        parent_resources=[
            ParentResource(model=Organization, field_name="organization"),
        ],
    ),
    ResourceConfig(
        User,
        shared_resource=SharedResource(
            serializer=UserType,
            is_provider=False,
        ),
        name_field="username",
    ),
]
