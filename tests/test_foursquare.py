"""Foursquare OS Places: pure SQL-building/row-mapping logic, no real S3/network call -
mirrors tests/test_discovery.py's Overture coverage."""

from gtm_engine.discovery.foursquare import build_sql, row_to_company
from gtm_engine.discovery.geocode import BBox


def test_foursquare_row_mapping_and_sql():
    sql, params = build_sql("2026-08-19", BBox(33.5, 72.8, 33.8, 73.2), ["clothing store", "shoe store"], 50)
    assert "release/dt=2026-08-19/places" in sql and "LIMIT 50" in sql
    assert "date_closed IS NULL" in sql
    assert params == ["%clothing store%", "%shoe store%"] and sql.count("LIKE ?") == 2

    c = row_to_company({"id": "abc", "name": "Cell Story", "category": ["mobile phone shop"],
                        "website": "http://www.cellstory.pk/", "email": "Info@CellStory.pk",
                        "phone": "051-1234567", "address": "Blue Area", "country": "PK",
                        "lat": 33.7, "lon": 73.0}, "Islamabad", "Pakistan")
    assert c.source == "foursquare" and c.category == "foursquare=mobile phone shop"
    assert c.email == "info@cellstory.pk" and c.city == "Islamabad" and c.country == "Pakistan"
    assert c.source_url == "https://foursquare.com/v/abc"

    assert row_to_company({"name": ""}, "Islamabad", "Pakistan") is None


def test_foursquare_no_categories_yields_empty_clause():
    sql, params = build_sql("2026-08-19", BBox(33.5, 72.8, 33.8, 73.2), [], 10)
    assert "LIKE" not in sql and params == []


def test_foursquare_row_without_category_or_id():
    c = row_to_company({"name": "No Category Shop"}, "Lahore", "Pakistan")
    assert c.category is None and c.source_url is None
