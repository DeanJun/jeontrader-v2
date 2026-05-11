import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # KIS API
    kis_mode: Mapped[str] = mapped_column(String(10), default="paper")  # "paper" | "real"
    kis_customer_id: Mapped[str | None] = mapped_column(String(50))
    kis_app_key: Mapped[str | None] = mapped_column(String(255))
    kis_app_secret: Mapped[str | None] = mapped_column(String(255))
    kis_account_no: Mapped[str | None] = mapped_column(String(50))

    # 텔레그램
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50), unique=True)
    telegram_link_code: Mapped[str | None] = mapped_column(String(10))  # 연동용 6자리 코드

    # 트레이딩 설정
    notify_only: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    privacy_agreed: Mapped[bool] = mapped_column(Boolean, default=False)

    # 트레이딩 상태 (메모리와 동기화)
    kis_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kis_split: Mapped[int] = mapped_column(Integer, default=1)  # 1 | 2 | 4
    kis_buy_count: Mapped[int] = mapped_column(Integer, default=0)
    kis_position: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"AAPL": "long"}

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
