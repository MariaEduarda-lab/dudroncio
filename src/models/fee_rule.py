from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint, func

from models.base import Base


class FeeRule(Base):
    """Preco de um tipo de envio para um tipo de cliente, a partir de uma data.

    A tabela nunca e editada nem apagada (TAR-14): um preco novo e uma linha
    nova com outro valid_from, e a vigente e a de maior valid_from ate o
    instante consultado.
    """

    __tablename__ = "fee_rule"

    id = Column(BigInteger, primary_key=True)
    person_type = Column(String(2), nullable=False)
    transaction_type = Column(String(20), nullable=False)
    free_monthly_quota = Column(Integer, nullable=False)
    fee_cents = Column(BigInteger, nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("person_type", "transaction_type", "valid_from", name="uq_fee_rule"),)
