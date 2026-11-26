from fastapi import APIRouter, Query
from sqlalchemy import select

from app.models import Laptop
from app.routers.common import DB, NOT_FOUND, get_laptop_or_404
from app.schemas import LaptopDetail, LaptopSummary, TicketSummary

router = APIRouter(prefix="/api/laptops", tags=["laptops"])


@router.get("", response_model=list[LaptopSummary])
def search_laptops(
    db: DB, query: str = Query("", description="Device ID or serial number, partial match")
):
    stmt = select(Laptop).order_by(Laptop.device_id)
    q = query.strip()
    if q:
        stmt = stmt.where(Laptop.device_id.ilike(f"%{q}%") | Laptop.serial_number.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.get("/{device_id}", response_model=LaptopDetail, responses=NOT_FOUND)
def get_laptop(device_id: str, db: DB):
    """Laptop with the customer it belongs to."""
    return get_laptop_or_404(db, device_id)


@router.get("/{device_id}/tickets", response_model=list[TicketSummary], responses=NOT_FOUND)
def laptop_tickets(device_id: str, db: DB):
    return get_laptop_or_404(db, device_id).tickets
