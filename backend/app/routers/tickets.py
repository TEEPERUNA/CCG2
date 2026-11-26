from fastapi import APIRouter, HTTPException

from app.models import Ticket
from app.routers.common import DB, NOT_FOUND
from app.schemas import TicketDetail

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("/{ticket_id}", response_model=TicketDetail, responses=NOT_FOUND)
def get_ticket(ticket_id: str, db: DB):
    """Ticket with its customer and, when linked, its laptop (laptop is null otherwise)."""
    ticket = db.get(Ticket, ticket_id.strip().upper())
    if ticket is None:
        raise HTTPException(404, f"Ticket {ticket_id} not found")
    return ticket
