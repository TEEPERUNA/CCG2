"""Business rules. Kept out of the routers so they can be unit-tested directly."""

import re
from datetime import date

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.models import Agreement, GuideVersion

# --- Agreements ----------------------------------------------------------------------------


def agreement_in_force(agreement: Agreement, on: date) -> bool:
    """Both ends are inclusive (sample-data README: 'Agreement end dates are inclusive')."""
    return agreement.valid_from <= on <= agreement.valid_until


def pick_agreement_in_force(agreements: list[Agreement], on: date) -> Agreement | None:
    active = [a for a in agreements if agreement_in_force(a, on)]
    # Overlaps should not exist; if they do, the most recently started one wins.
    return max(active, key=lambda a: a.valid_from, default=None)


# --- Guides --------------------------------------------------------------------------------

# Drafts never count as in force, whatever their dates say.
EFFECTIVE_STATUSES = ("published", "archived")


def _effective_on(on: date):
    return (
        GuideVersion.status.in_(EFFECTIVE_STATUSES),
        GuideVersion.effective_from.is_not(None),
        GuideVersion.effective_from <= on,
        or_(GuideVersion.effective_until.is_(None), GuideVersion.effective_until >= on),
    )


def guide_version_on(db: Session, guide_id: str, on: date) -> GuideVersion | None:
    """The version of a guide that was in force on a given date."""
    stmt = (
        select(GuideVersion)
        .where(GuideVersion.guide_id == guide_id, *_effective_on(on))
        .order_by(GuideVersion.effective_from.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def search_guides(db: Session, query: str, on: date) -> list[GuideVersion]:
    """Keyword search over the versions in force on `on`.

    PostgreSQL: full-text search with ranking. SQLite (dev/tests): case-insensitive LIKE.
    """
    effective = select(GuideVersion).where(*_effective_on(on))
    if not query.strip():
        return list(db.scalars(effective.order_by(GuideVersion.title)))

    if db.bind.dialect.name == "postgresql":
        # Title matches (weight A) rank above body matches (weight B).
        title = func.setweight(
            func.to_tsvector("english", GuideVersion.title), literal_column("'A'")
        )
        body = func.setweight(
            func.to_tsvector("english", GuideVersion.content_md), literal_column("'B'")
        )
        doc = title.op("||")(body)
        tsq = func.websearch_to_tsquery("english", query)
        stmt = effective.where(doc.op("@@")(tsq)).order_by(
            func.ts_rank(doc, tsq).desc(), GuideVersion.title
        )
        return list(db.scalars(stmt))

    terms = [t for t in re.split(r"\s+", query.strip()) if t]
    conds = [
        or_(GuideVersion.title.ilike(f"%{t}%"), GuideVersion.content_md.ilike(f"%{t}%"))
        for t in terms
    ]
    return list(db.scalars(effective.where(*conds).order_by(GuideVersion.title)))


def make_snippet(markdown: str, query: str, width: int = 160) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)  # links -> link text
    text = re.sub(r"[#*_`>]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    terms = [t.lower() for t in query.split() if t]
    pos = min((text.lower().find(t) for t in terms if t in text.lower()), default=0)
    start = max(0, pos - width // 3)
    snippet = text[start : start + width]
    return ("…" if start else "") + snippet + ("…" if start + width < len(text) else "")
