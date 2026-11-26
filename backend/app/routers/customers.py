from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from app.models import Customer
from app.routers.common import (
    DB,
    NOT_FOUND,
    OnDate,
    agreement_detail,
    agreement_summary,
    get_customer_or_404,
    resolve_date,
)
from app.schemas import (
    AgreementDetail,
    AgreementSummary,
    CustomerDetail,
    CustomerSummary,
    LaptopSummary,
    TicketSummary,
)
from app.services import pick_agreement_in_force

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerSummary])
def search_customers(
    db: DB,
    query: str = Query("", description="Organisation name or customer ID, partial match"),
):
    stmt = select(Customer).order_by(Customer.organisation_name)
    q = query.strip()
    if q:
        stmt = stmt.where(
            or_(Customer.customer_id.ilike(f"%{q}%"), Customer.organisation_name.ilike(f"%{q}%"))
        )
    return db.scalars(stmt).all()


@router.get("/{customer_id}", response_model=CustomerDetail, responses=NOT_FOUND)
def get_customer(customer_id: str, db: DB, on: OnDate = None):
    """Full customer record: laptops, agreements (with the one in force), tickets."""
    day = resolve_date(on)
    c = get_customer_or_404(db, customer_id)
    current = pick_agreement_in_force(c.agreements, day)
    return CustomerDetail(
        **CustomerSummary.model_validate(c).model_dump(),
        as_of=day,
        laptops=[LaptopSummary.model_validate(x) for x in c.laptops],
        agreements=[agreement_summary(a, day) for a in c.agreements],
        agreement_in_force=agreement_detail(current, day) if current else None,
        tickets=[TicketSummary.model_validate(t) for t in c.tickets],
    )


@router.get("/{customer_id}/laptops", response_model=list[LaptopSummary], responses=NOT_FOUND)
def customer_laptops(customer_id: str, db: DB):
    return get_customer_or_404(db, customer_id).laptops


@router.get("/{customer_id}/tickets", response_model=list[TicketSummary], responses=NOT_FOUND)
def customer_tickets(customer_id: str, db: DB):
    return get_customer_or_404(db, customer_id).tickets


@router.get("/{customer_id}/agreements", response_model=list[AgreementSummary], responses=NOT_FOUND)
def customer_agreements(customer_id: str, db: DB, on: OnDate = None):
    day = resolve_date(on)
    return [agreement_summary(a, day) for a in get_customer_or_404(db, customer_id).agreements]


@router.get(
    "/{customer_id}/agreements/in-force", response_model=AgreementDetail, responses=NOT_FOUND
)
def customer_agreement_in_force(customer_id: str, db: DB, on: OnDate = None):
    day = resolve_date(on)
    c = get_customer_or_404(db, customer_id)
    a = pick_agreement_in_force(c.agreements, day)
    if a is None:
        raise HTTPException(404, f"No agreement in force for {c.customer_id} on {day}")
    return agreement_detail(a, day)
