from sqlalchemy import BigInteger, Column, Date, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Client(Base):
    """Cliente PF ou PJ numa tabela so; os campos de cada tipo sao opcionais
    aqui e obrigatorios pelos CHECKs do database.sql."""

    __tablename__ = "client"

    id = Column(BigInteger, primary_key=True)
    client_key = Column(UUID(as_uuid=True), nullable=False)
    person_type = Column(String(2), nullable=False)
    document_number = Column(String(14), nullable=False)
    full_name = Column(String(255))
    birthdate = Column(Date)
    password_hash = Column(String(255))
    legal_name = Column(String(255))
    trade_name = Column(String(255))
    cnpj_status = Column(String(30))
    primary_activity = Column(String(255))
    monthly_income_cents = Column(BigInteger, nullable=False)
    email = Column(String(255), nullable=False)
    phone_number = Column(String(16), nullable=False)
    address = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("client_key", name="uq_client_key"),
        UniqueConstraint("document_number", name="uq_client_document"),
        UniqueConstraint("email", name="uq_client_email"),
    )

    legal_representatives = relationship(
        "LegalRepresentative",
        back_populates="client",
        order_by="asc(LegalRepresentative.id)",
    )
    account = relationship("Account", back_populates="client", uselist=False)

    PF = "PF"
    PJ = "PJ"
