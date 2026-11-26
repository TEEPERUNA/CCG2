from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.models import Guide, GuideVersion
from app.routers.common import DB, NOT_FOUND, OnDate, resolve_date
from app.schemas import GuideDetail, GuideSearchHit, GuideVersionSummary
from app.services import guide_version_on, make_snippet, search_guides

router = APIRouter(prefix="/api/guides", tags=["guides"])


@router.get("", response_model=list[GuideSearchHit])
def search(db: DB, query: str = Query("", description="Keywords"), on: OnDate = None):
    """Search the guide versions in force on `on` (default today). Drafts are never returned."""
    day = resolve_date(on)
    return [
        GuideSearchHit(
            **GuideVersionSummary.model_validate(v).model_dump(),
            snippet=make_snippet(v.content_md, query),
        )
        for v in search_guides(db, query, day)
    ]


@router.get("/{guide_id}", response_model=GuideDetail, responses=NOT_FOUND)
def get_guide(guide_id: str, db: DB, on: OnDate = None):
    """The version in force on `on` (default today). Use `on` for historical questions."""
    day = resolve_date(on)
    gid = guide_id.strip().upper()
    guide = db.get(Guide, gid)
    if guide is None:
        raise HTTPException(404, f"Guide {guide_id} not found")
    version = guide_version_on(db, gid, day)
    if version is None:
        raise HTTPException(404, f"No version of {gid} was in force on {day}")
    return GuideDetail(
        **GuideVersionSummary.model_validate(version).model_dump(),
        content_md=version.content_md,
        as_of=day,
        other_versions=[
            GuideVersionSummary.model_validate(v) for v in guide.versions if v.id != version.id
        ],
    )


@router.get("/{guide_id}/versions", response_model=list[GuideVersionSummary], responses=NOT_FOUND)
def list_versions(guide_id: str, db: DB):
    """All versions including archived and draft, for the version history view."""
    gid = guide_id.strip().upper()
    if db.get(Guide, gid) is None:
        raise HTTPException(404, f"Guide {guide_id} not found")
    stmt = select(GuideVersion).where(GuideVersion.guide_id == gid).order_by(GuideVersion.id)
    return db.scalars(stmt).all()


@router.get("/{guide_id}/versions/{version}", response_model=GuideDetail, responses=NOT_FOUND)
def get_version(guide_id: str, version: str, db: DB):
    """A specific version, whatever its status. The client must label drafts and archives."""
    gid = guide_id.strip().upper()
    v = db.scalars(
        select(GuideVersion).where(GuideVersion.guide_id == gid, GuideVersion.version == version)
    ).first()
    if v is None:
        raise HTTPException(404, f"Version {version} of {guide_id} not found")
    others = db.scalars(
        select(GuideVersion).where(GuideVersion.guide_id == gid, GuideVersion.id != v.id)
    ).all()
    return GuideDetail(
        **GuideVersionSummary.model_validate(v).model_dump(),
        content_md=v.content_md,
        as_of=v.effective_from or v.updated,
        other_versions=[GuideVersionSummary.model_validate(o) for o in others],
    )
