from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.orm import undefer

from app.models import Agreement
from app.routers.common import DB, NOT_FOUND, OnDate, agreement_detail, resolve_date
from app.schemas import AgreementDetail

router = APIRouter(prefix="/api/agreements", tags=["agreements"])


def _get(db, agreement_id: str, with_pdf: bool = False) -> Agreement:
    opts = [undefer(Agreement.pdf_content)] if with_pdf else []
    a = db.get(Agreement, agreement_id.strip().upper(), options=opts)
    if a is None:
        raise HTTPException(404, f"Agreement {agreement_id} not found")
    return a


@router.get("/{agreement_id}", response_model=AgreementDetail, responses=NOT_FOUND)
def get_agreement(agreement_id: str, db: DB, on: OnDate = None):
    return agreement_detail(_get(db, agreement_id), resolve_date(on))


@router.get(
    "/{agreement_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}, **NOT_FOUND},
)
def get_agreement_pdf(agreement_id: str, db: DB):
    a = _get(db, agreement_id, with_pdf=True)
    return Response(
        content=a.pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{a.pdf_filename}"'},
    )
