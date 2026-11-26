from datetime import date

import pytest
from sqlalchemy.orm import Session

from scripts.seed_dev import ImportError_, load
from tests.conftest import SAMPLE

FRIDAY = "2026-11-20"


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}


# --- Customers -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "q,expected",
    [
        ("west quay", ["CUST-002"]),
        ("cust-003", ["CUST-003"]),
        ("", ["CUST-001", "CUST-003", "CUST-002"]),  # ordered by name
    ],
)
def test_customer_search(client, q, expected):
    r = client.get("/api/customers", params={"query": q})
    assert [c["customer_id"] for c in r.json()] == expected


def test_customer_record_has_everything(client):
    c = client.get("/api/customers/CUST-002", params={"on": FRIDAY}).json()
    assert [x["device_id"] for x in c["laptops"]] == ["LT-1041", "LT-1042", "LT-1043", "LT-1044"]
    assert {a["agreement_id"]: a["in_force"] for a in c["agreements"]} == {
        "AGR-002-2026B": True,
        "AGR-002-2026A": False,
    }
    assert c["agreement_in_force"]["support_plan"] == "Premium"
    assert "One loan laptop is included" in c["agreement_in_force"]["loan_laptop_coverage"]
    assert [t["ticket_id"] for t in c["tickets"]] == ["HD-230", "HD-218", "HD-214"]


def test_unknown_customer_404(client):
    r = client.get("/api/customers/CUST-999")
    assert r.status_code == 404 and r.json() == {"detail": "Customer CUST-999 not found"}


def test_bad_date_422(client):
    assert client.get("/api/customers/CUST-002", params={"on": "friday"}).status_code == 422


# --- Laptops and tickets -------------------------------------------------------------------


def test_laptop_lookup_shows_customer(client):
    lt = client.get("/api/laptops/lt-1042").json()  # case-insensitive
    assert lt["customer"]["organisation_name"] == "West Quay Accounting"
    assert lt["status"] == "in_repair"


def test_laptop_tickets(client):
    r = client.get("/api/laptops/LT-1042/tickets").json()
    assert [t["ticket_id"] for t in r] == ["HD-230", "HD-218"]


def test_ticket_without_laptop(client):
    t = client.get("/api/tickets/HD-210").json()
    assert t["laptop"] is None and t["device_id"] is None
    assert t["customer"]["customer_id"] == "CUST-003"


# --- Agreements ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "on,expected",
    [
        ("2026-09-30", "AGR-002-2026A"),  # end date is inclusive
        ("2026-10-01", "AGR-002-2026B"),
        (FRIDAY, "AGR-002-2026B"),
    ],
)
def test_agreement_in_force_boundaries(client, on, expected):
    r = client.get("/api/customers/CUST-002/agreements/in-force", params={"on": on})
    assert r.json()["agreement_id"] == expected


def test_no_agreement_in_force(client):
    r = client.get("/api/customers/CUST-003/agreements/in-force", params={"on": "2026-02-01"})
    assert r.status_code == 404


def test_compare_loan_eligibility(client):
    a1 = client.get("/api/customers/CUST-001/agreements/in-force", params={"on": FRIDAY}).json()
    a2 = client.get("/api/customers/CUST-002/agreements/in-force", params={"on": FRIDAY}).json()
    assert "no loan entitlement" in a1["loan_laptop_coverage"]
    assert "duty technician" in a2["after_hours_handling"]


def test_pdf_download(client):
    r = client.get("/api/agreements/AGR-002-2026B/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


# --- Guides --------------------------------------------------------------------------------


def test_guide_search_returns_only_effective_versions(client):
    hits = client.get("/api/guides", params={"query": "pickup", "on": FRIDAY}).json()
    assert [(h["guide_id"], h["version"]) for h in hits] == [("GUIDE-101", "2.0")]


def test_after_hours_guide(client):
    hits = client.get("/api/guides", params={"query": "after hours", "on": FRIDAY}).json()
    assert "GUIDE-103" in [h["guide_id"] for h in hits]
    g = client.get("/api/guides/GUIDE-103").json()
    assert g["content_md"].startswith("# After-hours support")


@pytest.mark.parametrize(
    "on,version,office",
    [
        ("2026-11-12", "1.0", "Office A"),
        ("2026-11-16", "2.0", "Office B"),
        ("2027-06-01", "2.0", "Office B"),  # the draft never takes effect
    ],
)
def test_pickup_location_over_time(client, on, version, office):
    g = client.get("/api/guides/GUIDE-101", params={"on": on}).json()
    assert g["version"] == version and office in g["content_md"]


def test_version_history_includes_draft(client):
    v = client.get("/api/guides/GUIDE-101/versions").json()
    assert {x["version"]: x["status"] for x in v} == {
        "1.0": "archived",
        "2.0": "published",
        "3.0": "draft",
    }


def test_guide_links_rewritten(client):
    g = client.get("/api/guides/GUIDE-102").json()
    assert "(guide:GUIDE-101)" in g["content_md"] and ".md)" not in g["content_md"]


# --- Importer rules ------------------------------------------------------------------------


def test_importer_rejects_ticket_customer_mismatch(tmp_path):
    import json
    import shutil

    from app.db import Base, make_engine

    shutil.copytree(SAMPLE, tmp_path / "s")
    p = tmp_path / "s" / "data" / "support-tickets.json"
    tickets = json.loads(p.read_text())
    tickets[0]["device_id"] = "LT-1042"  # belongs to CUST-002, ticket is CUST-001
    p.write_text(json.dumps(tickets))

    eng = make_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as s, pytest.raises(ImportError_, match="belongs to CUST-002"):
        load(s, tmp_path / "s")


# --- The Friday-evening demo scenario ------------------------------------------------------


def test_friday_evening_scenario(client):
    laptop = client.get("/api/laptops/LT-1042").json()
    cust = client.get(f"/api/customers/{laptop['customer_id']}", params={"on": FRIDAY}).json()
    agr = cust["agreement_in_force"]
    assert agr["agreement_id"] == "AGR-002-2026B"
    assert "loan laptop is included" in agr["loan_laptop_coverage"]
    history = client.get("/api/laptops/LT-1042/tickets").json()
    assert "HD-218" in [t["ticket_id"] for t in history]
    guide = client.get("/api/guides/GUIDE-103", params={"on": FRIDAY}).json()
    assert guide["status"] == "published"
    assert date.fromisoformat(guide["as_of"]) == date(2026, 11, 20)
