"""The public-store slice of the demo, safe for STAGING (no orders, payments or finance entries).

Selected from the local demo content (one source of truth, `local_extras`): the consumer
categories marked B2C_ALLOWED, and the unrestricted consumer products of three fictional retail
sellers that the staging dataset already creates (`market.COMPANIES`). The local-only contrast
sellers (suspended, pending, rejected) stay in the local demo.
"""

from . import local_extras as _lx

# Seller key (a `market.COMPANIES` key) -> retail business type it sells under.
STORE_SELLERS = {
    key: _lx.COMPANY_BUSINESS_TYPES[key]
    for key in ("rehab-mobility", "aman-consumables", "sharq-devices")
}

_CONSUMER_SLUGS = frozenset(_lx.COMPLIANCE_CLASSES["B2C_ALLOWED"])

# (index in local_extras.EXTRA_CATEGORIES, row): the index keeps sort_order identical to the
# local demo, which creates the same categories under the same registry keys.
STORE_CATEGORIES = [
    (n, row) for n, row in enumerate(_lx.EXTRA_CATEGORIES) if row[0] in _CONSUMER_SLUGS
]

STORE_PRODUCTS = [
    row
    for row in _lx.EXTRA_PRODUCTS
    if row[1] in STORE_SELLERS
    and row[6] in ("B2C", "BOTH")
    and row[7] is False
    and row[2] in _CONSUMER_SLUGS
]

product_image_name = _lx.product_image_name
