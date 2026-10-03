from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from models.base import Base


class ClientStatusEvent(Base):
    __tablename__ = "client_status_event"

    id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, ForeignKey("client.id"), nullable=False)
    previous_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    reason = Column(String(255), nullable=False)
    event_datetime = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    client = relationship("Client", back_populates="status_events")
