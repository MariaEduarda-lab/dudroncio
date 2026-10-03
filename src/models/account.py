from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Account(Base):
    __tablename__ = "account"

    id = Column(BigInteger, primary_key=True)
    account_key = Column(UUID(as_uuid=True), nullable=False)
    client_id = Column(BigInteger, ForeignKey("client.id"), nullable=False)
    branch = Column(CHAR(4), nullable=False, server_default="0001")
    account_number = Column(CHAR(8), nullable=False)
    check_digit = Column(CHAR(1), nullable=False)
    balance_cents = Column(BigInteger, nullable=False, server_default="0")
    status = Column(String(20), nullable=False)
    status_reason = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("account_key", name="uq_account_key"),
        UniqueConstraint("client_id", name="uq_account_client"),
        UniqueConstraint("branch", "account_number", name="uq_account_number"),
    )

    client = relationship("Client", back_populates="account")

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    CLOSED = "CLOSED"
