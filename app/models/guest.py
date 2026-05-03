from datetime import datetime, UTC
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Guest(Base):
    __tablename__ = "guests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    invite_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    invited_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_matched_telegram_contact: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    event = relationship("Event", back_populates="guests")

    messages = relationship(
        "Message",
        back_populates="guest",
        cascade="all, delete-orphan",
    )

    rsvps = relationship(
        "Rsvp",
        back_populates="guest",
        cascade="all, delete-orphan",
    )