from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class AccountMovement(Base):
    """Efeito financeiro imutável de uma transação sobre uma conta."""

    __tablename__ = "account_movement"

    id = Column(BigInteger, primary_key=True)
    movement_key = Column(UUID(as_uuid=True), nullable=False)
    account_id = Column(BigInteger, ForeignKey("account.id"), nullable=False)
    transaction_id = Column(BigInteger, ForeignKey("transaction.id"), nullable=False)
    direction = Column(String(10), nullable=False)
    movement_type = Column(String(10), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    balance_after_cents = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("movement_key", name="uq_account_movement_key"),)

    account = relationship("Account", back_populates="account_movements")
    transaction = relationship("Transaction", back_populates="account_movements")

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    PRINCIPAL = "PRINCIPAL"
    FEE = "FEE"
