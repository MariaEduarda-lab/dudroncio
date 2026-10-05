from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.base import Base


class TariffRule(Base):
    """Regra de tarifa versionada por tipo de pessoa, operação e direção."""

    __tablename__ = "tariff_rule"

    id = Column(BigInteger, primary_key=True)
    person_type = Column(String(2), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    direction = Column(String(3), nullable=False)
    monthly_free_quota = Column(Integer)
    fee_after_quota_cents = Column(BigInteger, nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "person_type",
            "transaction_type",
            "direction",
            "valid_from",
            name="uq_tariff_rule",
        ),
    )

    transactions = relationship("Transaction", back_populates="tariff_rule")

    IN = "IN"
    OUT = "OUT"
