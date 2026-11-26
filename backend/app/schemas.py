"""API contract. Share this module with the client so both sides use the same shapes."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Customers -----------------------------------------------------------------------------


class CustomerSummary(ORM):
    customer_id: str
    organisation_name: str
    support_email: str
    site: str


# --- Laptops -------------------------------------------------------------------------------


class LaptopSummary(ORM):
    device_id: str
    customer_id: str
    manufacturer: str
    model: str
    serial_number: str
    operating_system: str
    site: str
    status: str


class LaptopDetail(LaptopSummary):
    customer: CustomerSummary


# --- Tickets -------------------------------------------------------------------------------


class TicketSummary(ORM):
    ticket_id: str
    customer_id: str
    device_id: str | None
    opened_at: datetime
    title: str
    status: str


class TicketDetail(TicketSummary):
    description: str
    resolution: str | None
    customer: CustomerSummary
    laptop: LaptopSummary | None


# --- Agreements ----------------------------------------------------------------------------


class AgreementSummary(ORM):
    agreement_id: str
    customer_id: str
    title: str
    support_plan: str
    valid_from: date
    valid_until: date
    in_force: bool
    pdf_url: str


class AgreementDetail(AgreementSummary):
    staffed_hours: str | None
    loan_laptop_coverage: str | None
    after_hours_handling: str | None


# --- Customer record -----------------------------------------------------------------------


class CustomerDetail(CustomerSummary):
    as_of: date
    laptops: list[LaptopSummary]
    agreements: list[AgreementSummary]
    agreement_in_force: AgreementDetail | None
    tickets: list[TicketSummary]


# --- Guides --------------------------------------------------------------------------------


class GuideVersionSummary(ORM):
    guide_id: str
    version: str
    title: str
    status: str
    effective_from: date | None
    effective_until: date | None
    updated: date | None


class GuideSearchHit(GuideVersionSummary):
    snippet: str


class GuideDetail(GuideVersionSummary):
    content_md: str
    as_of: date
    other_versions: list[GuideVersionSummary]


# --- Misc ----------------------------------------------------------------------------------


class Health(BaseModel):
    status: str
    database: str


class ErrorResponse(BaseModel):
    detail: str
