from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(BigInteger, primary_key=True)
    transaction_key = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(20), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    fee_cents = Column(BigInteger, nullable=False, server_default="0")
    fee_rule_id = Column(BigInteger, ForeignKey("fee_rule.id"))
    source_account_id = Column(BigInteger, ForeignKey("account.id"))
    destination_account_id = Column(BigInteger, ForeignKey("account.id"))
    idempotency_key = Column(String(64))
    request_hash = Column(CHAR(64))
    external_id = Column(String(64))
    counterparty_name = Column(String(255), nullable=False)
    counterparty_document = Column(String(14), nullable=False)
    counterparty_bank_code = Column(CHAR(3), nullable=False)
    counterparty_branch = Column(String(4), nullable=False)
    counterparty_account_number = Column(String(20), nullable=False)
    pix_key = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("transaction_key", name="uq_transaction_key"),)

    source_account = relationship("Account", foreign_keys=[source_account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])

    TED_IN = "TED_IN"
    PIX_IN = "PIX_IN"
    PIX_OUT = "PIX_OUT"
    TED_OUT = "TED_OUT"
