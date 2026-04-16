from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    """Tenant identity and metadata resolved from Cognito groups and DynamoDB."""

    customer_id: str
    customer_name: str
