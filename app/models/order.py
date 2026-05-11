import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" | "sell"
    qty: Mapped[float | None] = mapped_column(Numeric(18, 6))
    price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    order_no: Mapped[str | None] = mapped_column(String(50))  # KIS 주문번호

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
