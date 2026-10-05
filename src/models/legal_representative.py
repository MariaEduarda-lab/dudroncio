from sqlalchemy import BigInteger, CHAR, Column, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class LegalRepresentative(Base):
    __tablename__ = "legal_representative"

    id = Column(BigInteger, primary_key=True)
    representative_key = Column(UUID(as_uuid=True), nullable=False)
    client_id = Column(BigInteger, ForeignKey("client.id"), nullable=False)
    cpf = Column(CHAR(11), nullable=False)
    full_name = Column(String(255), nullable=False)
    birthdate = Column(Date, nullable=False)
    email = Column(String(255), nullable=False)
    phone_number = Column(String(16), nullable=False)
    role = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("representative_key", name="uq_legal_representative_key"),
        UniqueConstraint("cpf", name="uq_legal_representative_cpf"),
        UniqueConstraint("email", name="uq_legal_representative_email"),
    )

    client = relationship("Client", back_populates="legal_representatives")
