"""Tests for HFC (Pikud HaOref) alert processing."""

import pytest


def test_hfc_zone_grouping():
    """Test that cities are grouped by zone correctly."""
    try:
        from app.services.hfc_zones import group_cities_by_zone

        cities = ["תל אביב - מרכז העיר", "אשקלון - דרום"]
        grouped = group_cities_by_zone(cities)
        assert isinstance(grouped, dict)
    except ImportError:
        pytest.skip("hfc_zones module not available")


def test_hfc_template_formatting():
    """Test that HFC templates render correctly."""
    try:
        from app.services.hfc_templates import apply_hfc_template

        template_data = {
            "timestamp": "12:00:00 01/01/2026",
            "zones_block": "Zone A: City1, City2",
            "cities_list": "City1, City2",
            "city_count": 2,
            "min_migun_time": "90 שניות",
            "max_migun_time": "90 שניות",
            "migun_display": "90 שניות",
            "guidance": "היכנסו למרחב מוגן",
            "alert_title": "ירי רקטות וטילים",
            "category_he": "ירי רקטות וטילים",
        }

        result = apply_hfc_template("rockets", template_data)
        assert isinstance(result, str)
        assert len(result) > 0
    except ImportError:
        pytest.skip("hfc_templates module not available")


def test_hfc_format_migun():
    """Test migun time formatting."""
    try:
        from app.services.hfc_alerts import _format_migun

        assert _format_migun(90) == "דקה וחצי"
        assert _format_migun(0) == "מיידי"
        assert _format_migun(None) == "מיידי"
        assert _format_migun(60) == "דקה"
        assert _format_migun(30) == "30 שניות"
        assert _format_migun(180) == "3 דקות"
    except ImportError:
        pytest.skip("hfc_alerts module not available")


def test_hfc_title_to_template_mapping():
    """Verify every _TITLE_TO_CATEGORY key maps to an existing template."""
    from app.services.hfc_alerts import _TITLE_TO_CATEGORY
    from app.services.hfc_templates import _default_hfc_templates

    templates = _default_hfc_templates()

    for title, info in _TITLE_TO_CATEGORY.items():
        key = info["key"]
        # Drill keys fall back to parent, so strip _drill suffix for lookup
        lookup = key.removesuffix("_drill") if key.endswith("_drill") else key
        assert lookup in templates, f"Title '{title}' maps to key '{key}' but no template exists for '{lookup}'"


def test_hfc_categories_have_templates():
    """Verify every HFC_CATEGORIES key maps to an existing template."""
    from app.services.hfc_alerts import HFC_CATEGORIES
    from app.services.hfc_templates import _default_hfc_templates

    templates = _default_hfc_templates()

    for matrix_id, info in HFC_CATEGORIES.items():
        key = info["key"]
        lookup = key.removesuffix("_drill") if key.endswith("_drill") else key
        assert lookup in templates, f"matrix_id '{matrix_id}' maps to key '{key}' but no template for '{lookup}'"


def test_hfc_special_titles_route_correctly():
    """Verify incident_resolved and all_clear route to their dedicated templates (not 'update')."""
    from app.services.hfc_alerts import _TITLE_TO_CATEGORY

    resolved = _TITLE_TO_CATEGORY.get("האירוע הסתיים")
    assert resolved is not None, "Missing mapping for 'האירוע הסתיים'"
    assert resolved["key"] == "incident_resolved", (
        f"'האירוע הסתיים' should map to 'incident_resolved', got '{resolved['key']}'"
    )

    all_clear = _TITLE_TO_CATEGORY.get("ניתן לצאת ממרחב מוגן")
    assert all_clear is not None, "Missing mapping for 'ניתן לצאת ממרחב מוגן'"
    assert all_clear["key"] == "all_clear", (
        f"'ניתן לצאת ממרחב מוגן' should map to 'all_clear', got '{all_clear['key']}'"
    )

    early = _TITLE_TO_CATEGORY.get("התרעה מוקדמת")
    assert early is not None, "Missing mapping for 'התרעה מוקדמת'"
    assert early["key"] == "early_warning", f"'התרעה מוקדמת' should map to 'early_warning', got '{early['key']}'"


def test_hfc_incident_resolved_template_no_redundancy():
    """Verify the incident_resolved template doesn't repeat 'האירוע הסתיים' multiple times."""
    from app.services.hfc_templates import apply_hfc_template

    result = apply_hfc_template(
        "incident_resolved",
        {
            "timestamp": "12:00:00 01/01/2026",
            "zones_block": "Zone A: City1",
            "category_he": "האירוע הסתיים",
            "alert_title": "האירוע הסתיים",
            "guidance": "",
        },
    )
    # Should appear at most twice (once in header, once is OK) but not three times
    count = result.count("האירוע הסתיים")
    assert count <= 2, f"'האירוע הסתיים' appears {count} times — template is redundant"
