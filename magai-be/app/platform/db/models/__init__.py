"""Imports every model so ``Base.metadata`` is complete.

Alembic autogenerate and the test-suite ``create_all`` both rely on this module
pulling in the full model graph.
"""

from app.features.billing.models import UsageRecord
from app.features.integrations.models import Integration, IntegrationDelivery
from app.features.leads.models import Lead, LeadDelivery, LeadNote
from app.features.payments.models import Payment, Subscription
from app.features.users.models import (
    ApiKey,
    AuthToken,
    CustomDomain,
    User,
    WorkspaceBrand,
    WorkspaceInvite,
)
from app.features.widgets.models import (
    Widget,
    WidgetDeployment,
    WidgetHealEvent,
    WidgetInteraction,
)
from app.platform.pipeline.models import GenerationUsage

__all__ = [
    "ApiKey",
    "AuthToken",
    "CustomDomain",
    "GenerationUsage",
    "Integration",
    "IntegrationDelivery",
    "Lead",
    "LeadDelivery",
    "LeadNote",
    "Payment",
    "Subscription",
    "UsageRecord",
    "User",
    "Widget",
    "WidgetDeployment",
    "WidgetHealEvent",
    "WidgetInteraction",
    "WorkspaceBrand",
    "WorkspaceInvite",
]
