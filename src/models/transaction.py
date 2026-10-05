from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(BigInteger, primary_key=True)
    transaction_key = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(20), nullable=False)
    direction = Column(String(3), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    fee_cents = Column(BigInteger, nullable=False, server_default="0")
    tariff_rule_id = Column(BigInteger, ForeignKey("tariff_rule.id"), nullable=False)
    source_account_id = Column(BigInteger, ForeignKey("account.id"))
    destination_account_id = Column(BigInteger, ForeignKey("account.id"))
    requested_by_client_id = Column(BigInteger, ForeignKey("client.id"))
    requested_by_representative_id = Column(BigInteger, ForeignKey("legal_representative.id"))
    idempotency_key = Column(String(64))
    external_reference = Column(String(64))
    request_fingerprint = Column(CHAR(64))
    authorization_fingerprint = Column(CHAR(64))
    authorization_expires_at = Column(DateTime(timezone=True))
    authorization_method = Column(String(50))
    status = Column(String(20), nullable=False)
    status_reason = Column(String(255))
    counterparty_name = Column(String(255), nullable=False)
    counterparty_document = Column(String(14), nullable=False)
    counterparty_bank_code = Column(CHAR(3), nullable=False)
    counterparty_branch = Column(String(4), nullable=False)
    counterparty_account_number = Column(String(20), nullable=False)
    pix_key = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    validated_at = Column(DateTime(timezone=True))
    review_started_at = Column(DateTime(timezone=True))
    authorized_at = Column(DateTime(timezone=True))
    processing_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    blocked_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    reversed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("transaction_key", name="uq_transaction_key"),)

    source_account = relationship("Account", foreign_keys=[source_account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])
    requested_by_client = relationship("Client", foreign_keys=[requested_by_client_id])
    requested_by_representative = relationship("LegalRepresentative", foreign_keys=[requested_by_representative_id])
    tariff_rule = relationship("TariffRule", back_populates="transactions")
    risk_analyses = relationship("TransactionRiskAnalysis", back_populates="transaction", order_by="TransactionRiskAnalysis.id")
    account_movements = relationship("AccountMovement", back_populates="transaction", order_by="AccountMovement.id")

    PIX = "PIX"
    TED = "TED"
    IN = "IN"
    OUT = "OUT"

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    UNDER_REVIEW = "UNDER_REVIEW"
    AUTHORIZED = "AUTHORIZED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"
