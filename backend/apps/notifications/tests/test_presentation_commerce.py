import pytest

from apps.notifications.presentation import render


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_sponsored_and_promotion_alerts_are_labelled(lang):
    label = "إعلان ممول" if lang == "ar" else "Sponsored"
    title, body = render(
        "SPONSORED_PRODUCT",
        {"product_title": "كرسي أسنان | Dental chair", "company_name": "مكتب | Office"},
        lang,
    )
    assert title.startswith(label)
    assert ("كرسي أسنان" in body) if lang == "ar" else ("Dental chair" in body)
    title, _ = render("PROPERTY_PROMOTION", {"listing_title": "عيادة | Clinic"}, lang)
    assert title.startswith(label)


def test_order_and_quote_events_render_and_unknown_status_falls_back():
    assert render("ORDER_PLACED", {"status": "PLACED", "order_number": "RCH-1"}, "en") == (
        "Order received",
        "Order RCH-1.",
    )
    assert render("ORDER_STATUS_CHANGED", {"status": "SHIPPED"}, "ar")[0] == "تم شحن الطلب"
    assert render("QUOTE_UPDATED", {"status": "QUOTED", "product_title": "X"}, "en")[0] == (
        "Price quote received"
    )
    assert render("ORDER_STATUS_CHANGED", {"status": "BOGUS"}, "en") == ("New notification", "")
