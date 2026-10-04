from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Entry(Base):
    """Lancamento: uma mudanca de saldo, com o saldo que ficou depois dela."""

    __tablename__ = "entry"

    id = Column(BigInteger, primary_key=True)
    entry_key = Column(UUID(as_uuid=True), nullable=False)
    account_id = Column(BigInteger, ForeignKey("account.id"), nullable=False)
    transaction_id = Column(BigInteger, ForeignKey("transaction.id"), nullable=False)
    entry_type = Column(String(10), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    balance_after_cents = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("entry_key", name="uq_entry_key"),)

    transaction = relationship("Transaction")

    VALUE = "VALUE"
    FEE = "FEE"
