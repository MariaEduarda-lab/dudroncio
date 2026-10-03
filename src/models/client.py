from sqlalchemy import BigInteger, CHAR, Column, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from models.base import Base


class Client(Base):
    __tablename__ = "client"

    id = Column(BigInteger, primary_key=True)
    client_key = Column(CHAR(36), nullable=False)
    cnpj = Column(String(14), nullable=False)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255))
    client_type = Column(String(10), nullable=False)
    cnpj_status = Column(String(30), nullable=False)
    primary_activity = Column(String(255), nullable=False)
    monthly_revenue_cents = Column(BigInteger, nullable=False)
    email = Column(String(255), nullable=False)
    phone_number = Column(String(16), nullable=False)
    address = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("client_key", name="uq_client_key"),
        UniqueConstraint("cnpj", name="uq_client_cnpj"),
        UniqueConstraint("email", name="uq_client_email"),
    )

    legal_representatives = relationship(
        "LegalRepresentative",
        back_populates="client",
        order_by="asc(LegalRepresentative.id)",
    )
