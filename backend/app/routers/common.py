from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import today_helsinki
from app.db import get_session
from app.models import Agreement, Customer, Laptop
from app.schemas import AgreementDetail, AgreementSummary
from app.services import agreement_in_force

DB = Annotated[Session, Depends(get_session)]

OnDate = Annotated[
    date | None,
    Query(
        alias="on",
        description="Reference date (YYYY-MM-DD). Defaults to today in Europe/Helsinki.",
    ),
]

NOT_FOUND = {
    404: {
        "description": "Not found",
        "content": {"application/json": {"example": {"detail": "Laptop LT-9999 not found"}}},
    }
}


def resolve_date(on: date | None) -> date:
    return on or today_helsinki()


def get_customer_or_404(db: Session, customer_id: str) -> Customer:
    customer = db.get(Customer, customer_id.strip().upper())
    if customer is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return customer


def get_laptop_or_404(db: Session, device_id: str) -> Laptop:
    laptop = db.get(Laptop, device_id.strip().upper())
    if laptop is None:
        raise HTTPException(404, f"Laptop {device_id} not found")
    return laptop


def agreement_summary(a: Agreement, on: date) -> AgreementSummary:
    return AgreementSummary(
        agreement_id=a.agreement_id,
        customer_id=a.customer_id,
        title=a.title,
        support_plan=a.support_plan,
        valid_from=a.valid_from,
        valid_until=a.valid_until,
        in_force=agreement_in_force(a, on),
        pdf_url=f"/api/agreements/{a.agreement_id}/pdf",
    )


def agreement_detail(a: Agreement, on: date) -> AgreementDetail:
    return AgreementDetail(
        **agreement_summary(a, on).model_dump(),
        staffed_hours=a.staffed_hours,
        loan_laptop_coverage=a.loan_laptop_coverage,
        after_hours_handling=a.after_hours_handling,
    )
