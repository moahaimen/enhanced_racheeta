"""Per-account marketing preferences (docs/NOTIFICATIONS.md §Marketing preferences).

Two different things are recorded separately:

* DISPLAY preferences — whether sponsored content is shown inside Racheeta
  (`show_sponsored_products`, on by default for professionals because it is the product's
  targeted catalogue; it can be switched off);
* OUTREACH consent — whether the account wants marketing messages at all (`real_estate_promotions`,
  `job_alerts`, `offers_and_news`, all OFF by default) and on which channels (`channel_in_app` on,
  `channel_email` / `channel_push` off). Nothing is ever sent outside the app by this local demo.

Transactional notifications (reservations, orders, quotes, applications) never consult this
table: an opt-out never suppresses them.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class MarketingPreference(BaseModel):
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marketing_preference"
    )
    show_sponsored_products = models.BooleanField(default=True)
    real_estate_promotions = models.BooleanField(default=False)
    job_alerts = models.BooleanField(default=False)
    offers_and_news = models.BooleanField(default=False)
    channel_in_app = models.BooleanField(default=True)
    channel_email = models.BooleanField(default=False)
    channel_push = models.BooleanField(default=False)
    consent_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "preferences_marketing"

    def __str__(self) -> str:
        return f"preferences of {self.account_id}"


FIELDS = (
    "show_sponsored_products",
    "real_estate_promotions",
    "job_alerts",
    "offers_and_news",
    "channel_in_app",
    "channel_email",
    "channel_push",
)
# Defaults when an account has no row yet (must equal the field defaults above).
DEFAULTS = {
    "show_sponsored_products": True,
    "real_estate_promotions": False,
    "job_alerts": False,
    "offers_and_news": False,
    "channel_in_app": True,
    "channel_email": False,
    "channel_push": False,
}
