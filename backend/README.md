# Company Brain – Backend API (LXC 2)

FastAPI + SQLAlchemy 2 + PostgreSQL. Interactive docs at `/docs`, schema at `/openapi.json`.

## Run locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python -m scripts.seed_dev ../sample-data --reset   # SQLite file by default
uvicorn app.main:app --reload                        # http://127.0.0.1:8000/docs
pytest && ruff check .
```

Against PostgreSQL:

```bash
export DATABASE_URL="postgresql+psycopg://cb_api:<password>@10.10.10.13:5432/company_brain"
python -m scripts.seed_dev ../sample-data --reset
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Layout

| Path | Contents |
| --- | --- |
| `app/models.py` | SQLAlchemy tables |
| `app/schemas.py` | Pydantic response models = the API contract. Share these with the client. |
| `app/services.py` | Business rules: agreement in force, guide version on a date, search |
| `app/routers/` | One file per resource |
| `scripts/seed_dev.py` | Sample-data import with validation (reference for Person A's importer) |
| `tests/` | API tests covering the README demo scenarios |

## Business rules

- **Dates.** Every date-sensitive endpoint takes `?on=YYYY-MM-DD`. The default is today in Europe/Helsinki.
- **Agreement in force.** `valid_from <= on <= valid_until`, and both ends count. CUST-002 had Business until 2026-09-30 and Premium from 2026-10-01.
- **Guide version on a date.** The guide must be `published` or `archived`, and `on` must fall within `effective_from` and `effective_until` (an empty end date means it never ends). **Drafts never take effect.**
- **Guide links.** The importer rewrites `[text](after-hours-support.md)` to `[text](guide:GUIDE-103)`. The client opens `guide:` links inside the app.
- **Agreement PDF sections.** The importer extracts *Staffed support hours*, *Loan laptop coverage* and *After-hours handling*, so the client can show them without opening the PDF.
- **Search.** PostgreSQL uses full-text search, with title matches ranked first. SQLite uses `ILIKE`.

## Endpoints

All responses are JSON unless noted otherwise. Errors return `{"detail": "..."}`, with **404** for an unknown ID and **422** for bad input, such as `on=friday`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | `{"status":"ok","database":"ok"}`, or 503 |
| GET | `/api/customers?query=` | Search by name or ID (partial, case-insensitive) |
| GET | `/api/customers/{id}?on=` | Full record: laptops, agreements, `agreement_in_force`, tickets |
| GET | `/api/customers/{id}/laptops` | Laptops |
| GET | `/api/customers/{id}/tickets` | Tickets, newest first |
| GET | `/api/customers/{id}/agreements?on=` | All agreements, each with `in_force` |
| GET | `/api/customers/{id}/agreements/in-force?on=` | The agreement in force, or 404 |
| GET | `/api/laptops?query=` | Search by device ID or serial number |
| GET | `/api/laptops/{id}` | Laptop and its `customer` |
| GET | `/api/laptops/{id}/tickets` | Tickets for the laptop, newest first |
| GET | `/api/tickets/{id}` | Ticket, `customer`, and `laptop` (null when not linked) |
| GET | `/api/agreements/{id}?on=` | Agreement metadata and PDF sections |
| GET | `/api/agreements/{id}/pdf` | `application/pdf`, inline |
| GET | `/api/guides?query=&on=` | Search the versions in force, with a snippet |
| GET | `/api/guides/{id}?on=` | Version in force with `content_md` and `other_versions` |
| GET | `/api/guides/{id}/versions` | All versions, including archived and draft |
| GET | `/api/guides/{id}/versions/{version}` | One specific version, any status |

### Examples

`GET /api/laptops/LT-1042`
```json
{
  "device_id": "LT-1042", "customer_id": "CUST-002", "manufacturer": "Dell",
  "model": "Latitude 5450", "serial_number": "EI-SAMPLE-1042",
  "operating_system": "Windows 11 Pro", "site": "Central Office", "status": "in_repair",
  "customer": {"customer_id": "CUST-002", "organisation_name": "West Quay Accounting",
               "support_email": "it@westquay.example", "site": "Central Office"}
}
```

`GET /api/customers/CUST-002/agreements/in-force?on=2026-11-20`
```json
{
  "agreement_id": "AGR-002-2026B", "customer_id": "CUST-002", "title": "Premium IT support",
  "support_plan": "Premium", "valid_from": "2026-10-01", "valid_until": "2027-09-30",
  "in_force": true, "pdf_url": "/api/agreements/AGR-002-2026B/pdf",
  "staffed_hours": "Monday to Friday, 08:00-16:00. The Service Desk handles requests during those hours.",
  "loan_laptop_coverage": "One loan laptop is included for an eligible failed company laptop. The technician must confirm inventory and arrange pickup before giving the customer a pickup time.",
  "after_hours_handling": "The duty technician handles urgent laptop failures reported outside staffed hours. A blocked employee with no usable work device qualifies for escalation."
}
```

`GET /api/guides?query=after hours&on=2026-11-20`
```json
[
  {"guide_id": "GUIDE-103", "version": "1.0", "title": "After-hours support",
   "status": "published", "effective_from": "2026-10-01", "effective_until": null,
   "updated": null, "snippet": "After-hours support Check the agreement The Service Desk is staffed…"}
]
```

`GET /api/guides/GUIDE-101?on=2026-11-12` returns version `1.0` (archived, Office A). Without `on`, it returns `2.0` (published, Office B).

`GET /api/tickets/HD-210` returns `"device_id": null, "laptop": null` together with the customer.

## Deploy on LXC 2

See `deploy/company-brain-api.service`. Nginx (LXC 1) proxies `/api/` to `http://<lxc2>:8000`. PostgreSQL (LXC 3) should accept connections from LXC 2 only.
