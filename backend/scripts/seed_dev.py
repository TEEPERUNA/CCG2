"""Load the sample-data pack into the database.

Usage (from backend/):
    python -m scripts.seed_dev ../sample-data            # uses DATABASE_URL
    python -m scripts.seed_dev ../sample-data --reset    # drop + recreate tables first

Person A owns the production importer and Alembic migrations. This script is the
reference behaviour the API is tested against; reuse whatever helps.
"""

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import DATABASE_URL
from app.db import Base, make_engine
from app.models import (
    Agreement,
    Customer,
    Guide,
    GuideVersion,
    Laptop,
    LoanDevice,
    Ticket,
)


class ImportError_(Exception):
    pass


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _unique(rows: list[dict], key: str, what: str) -> None:
    seen = set()
    for r in rows:
        if r[key] in seen:
            raise ImportError_(f"Duplicate {what} {r[key]}")
        seen.add(r[key])


def _date(value) -> date | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


# --- PDF agreements ------------------------------------------------------------------------

PDF_SECTIONS = {
    "Staffed support hours": "staffed_hours",
    "Loan laptop coverage": "loan_laptop_coverage",
    "After-hours handling": "after_hours_handling",
}


def extract_pdf_sections(pdf_bytes_path: Path) -> dict[str, str]:
    text = "\n".join(p.extract_text() or "" for p in PdfReader(pdf_bytes_path).pages)
    out: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if line in PDF_SECTIONS:
            current = PDF_SECTIONS[line]
            out[current] = []
        elif current and line:
            out[current].append(line)
    return {k: " ".join(v) for k, v in out.items()}


# --- Markdown guides -----------------------------------------------------------------------

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)
MD_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")


def parse_guide(path: Path) -> tuple[dict, str]:
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not m:
        raise ImportError_(f"{path} has no front matter")
    meta = yaml.safe_load(m.group(1))
    for field in ("id", "title", "version", "status"):
        if field not in meta:
            raise ImportError_(f"{path} front matter is missing '{field}'")
    return meta, m.group(2).strip() + "\n"


def rewrite_links(body: str, file_to_guide: dict[str, str]) -> str:
    """'after-hours-support.md' -> 'guide:GUIDE-103'. The client opens guide: links in-app."""

    def repl(m: re.Match) -> str:
        gid = file_to_guide.get(Path(m.group(1)).name)
        return f"](guide:{gid})" if gid else m.group(0)

    return MD_LINK.sub(repl, body)


# --- Main ----------------------------------------------------------------------------------


def load(session: Session, root: Path) -> dict[str, int]:
    data = root / "data"
    customers = _csv(data / "customers.csv")
    laptops = _csv(data / "laptops.csv")
    tickets = json.loads((data / "support-tickets.json").read_text(encoding="utf-8"))
    agreements = _csv(data / "agreement-index.csv")

    _unique(customers, "customer_id", "customer")
    _unique(laptops, "device_id", "laptop")
    _unique(laptops, "serial_number", "serial number")
    _unique(tickets, "ticket_id", "ticket")
    _unique(agreements, "agreement_id", "agreement")

    cust_ids = {c["customer_id"] for c in customers}
    laptop_owner = {lt["device_id"]: lt["customer_id"] for lt in laptops}
    for row, what, key in (
        *((lt, "Laptop", "device_id") for lt in laptops),
        *((t, "Ticket", "ticket_id") for t in tickets),
        *((a, "Agreement", "agreement_id") for a in agreements),
    ):
        if row["customer_id"] not in cust_ids:
            raise ImportError_(f"{what} {row[key]} references unknown {row['customer_id']}")
    for t in tickets:
        dev = t.get("device_id")
        if dev is None:
            continue
        if dev not in laptop_owner:
            raise ImportError_(f"Ticket {t['ticket_id']} references unknown laptop {dev}")
        if laptop_owner[dev] != t["customer_id"]:
            raise ImportError_(
                f"Ticket {t['ticket_id']}: laptop {dev} belongs to {laptop_owner[dev]}, "
                f"not {t['customer_id']}"
            )
    for a in agreements:
        if _date(a["valid_until"]) < _date(a["valid_from"]):
            raise ImportError_(f"Agreement {a['agreement_id']} ends before it starts")

    session.add_all(Customer(**c) for c in customers)
    session.add_all(Laptop(**lt) for lt in laptops)
    session.add_all(
        Ticket(**{**t, "opened_at": datetime.fromisoformat(t["opened_at"])}) for t in tickets
    )

    for a in agreements:
        pdf = root / a["pdf_path"]
        if not pdf.is_file():
            raise ImportError_(f"Agreement {a['agreement_id']}: missing {a['pdf_path']}")
        session.add(
            Agreement(
                agreement_id=a["agreement_id"],
                customer_id=a["customer_id"],
                title=a["title"],
                support_plan=a["support_plan"],
                valid_from=_date(a["valid_from"]),
                valid_until=_date(a["valid_until"]),
                pdf_filename=pdf.name,
                pdf_content=pdf.read_bytes(),
                **extract_pdf_sections(pdf),
            )
        )

    guide_files = sorted((root / "guides").rglob("*.md"))
    parsed = [(p, *parse_guide(p)) for p in guide_files]
    file_to_guide = {p.name: meta["id"] for p, meta, _ in parsed}
    seen_versions = set()
    for p, meta, body in parsed:
        key = (meta["id"], str(meta["version"]))
        if key in seen_versions:
            raise ImportError_(f"Duplicate guide version {key} in {p}")
        seen_versions.add(key)
        if session.get(Guide, meta["id"]) is None:
            session.add(Guide(guide_id=meta["id"]))
            session.flush()
        session.add(
            GuideVersion(
                guide_id=meta["id"],
                version=str(meta["version"]),
                title=meta["title"],
                status=meta["status"],
                effective_from=_date(meta.get("effective_from")),
                effective_until=_date(meta.get("effective_until")),
                updated=_date(meta.get("updated")),
                content_md=rewrite_links(body, file_to_guide),
            )
        )

    inv = root / "optional" / "loan-inventory.csv"
    loans = _csv(inv) if inv.is_file() else []
    session.add_all(
        LoanDevice(**{**r, "last_checked_at": datetime.fromisoformat(r["last_checked_at"])})
        for r in loans
    )
    session.commit()
    return {
        "customers": len(customers),
        "laptops": len(laptops),
        "tickets": len(tickets),
        "agreements": len(agreements),
        "guide_versions": len(parsed),
        "loan_devices": len(loans),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="sample-data folder (the one with README.md)")
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    args = ap.parse_args()

    engine = make_engine(DATABASE_URL)
    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as s:
            counts = load(s, args.root)
    except ImportError_ as e:
        sys.exit(f"Import rejected: {e}")
    print("Imported:", ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
