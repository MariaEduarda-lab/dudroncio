from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from models.base import Base


class TransactionRiskAnalysis(Base):
    """Decisão imutável de uma avaliação de risco feita sobre a transação."""

    __tablename__ = "transaction_risk_analysis"

    id = Column(BigInteger, primary_key=True)
    transaction_id = Column(BigInteger, ForeignKey("transaction.id"), nullable=False)
    decision = Column(String(20), nullable=False)
    score = Column(Integer)
    reason_code = Column(String(100), nullable=False)
    reason_description = Column(String(255), nullable=False)
    engine_version = Column(String(100), nullable=False)
    analyzed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    transaction = relationship("Transaction", back_populates="risk_analyses")

    APPROVED = "APPROVED"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"
