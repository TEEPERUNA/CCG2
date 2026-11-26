from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    organisation_name: Mapped[str] = mapped_column(String(200), index=True)
    support_email: Mapped[str] = mapped_column(String(200))
    site: Mapped[str] = mapped_column(String(100))

    laptops: Mapped[list["Laptop"]] = relationship(
        back_populates="customer", order_by="Laptop.device_id"
    )
    agreements: Mapped[list["Agreement"]] = relationship(
        back_populates="customer", order_by="Agreement.valid_from.desc()"
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="customer", order_by="Ticket.opened_at.desc()"
    )


class Laptop(Base):
    __tablename__ = "laptops"

    device_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    manufacturer: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    serial_number: Mapped[str] = mapped_column(String(100), unique=True)
    operating_system: Mapped[str] = mapped_column(String(100))
    site: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))

    customer: Mapped[Customer] = relationship(back_populates="laptops")
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="laptop", order_by="Ticket.opened_at.desc()"
    )


class Ticket(Base):
    __tablename__ = "support_tickets"

    ticket_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("laptops.device_id"), index=True, nullable=True
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="tickets")
    laptop: Mapped[Laptop | None] = relationship(back_populates="tickets")


class Agreement(Base):
    __tablename__ = "support_agreements"

    agreement_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    support_plan: Mapped[str] = mapped_column(String(50))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)  # inclusive
    # Sections extracted from the PDF at import time, so the client can show them without
    # opening the file. The PDF stays the source of truth.
    staffed_hours: Mapped[str | None] = mapped_column(Text, nullable=True)
    loan_laptop_coverage: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_hours_handling: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_filename: Mapped[str] = mapped_column(String(200))
    pdf_content: Mapped[bytes] = deferred(mapped_column(LargeBinary))

    customer: Mapped[Customer] = relationship(back_populates="agreements")


class Guide(Base):
    __tablename__ = "guides"

    guide_id: Mapped[str] = mapped_column(String(20), primary_key=True)

    versions: Mapped[list["GuideVersion"]] = relationship(
        back_populates="guide", order_by="GuideVersion.effective_from"
    )


class GuideVersion(Base):
    __tablename__ = "guide_versions"
    __table_args__ = (UniqueConstraint("guide_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guide_id: Mapped[str] = mapped_column(ForeignKey("guides.guide_id"), index=True)
    version: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))  # published | archived | draft
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_until: Mapped[date | None] = mapped_column(Date, nullable=True)  # inclusive
    updated: Mapped[date | None] = mapped_column(Date, nullable=True)
    content_md: Mapped[str] = mapped_column(Text)

    guide: Mapped[Guide] = relationship(back_populates="versions")


class LoanDevice(Base):
    __tablename__ = "loan_inventory"

    loan_device_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    model: Mapped[str] = mapped_column(String(100))
    pickup_site: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
