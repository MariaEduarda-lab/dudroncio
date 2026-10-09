from datetime import datetime

from database import Context
from models import TariffRule


class TariffRuleRepository:
    """Consulta regras de tarifa versionadas; regras existentes são imutáveis."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_current_rule(
        self,
        person_type: str,
        transaction_type: str,
        direction: str,
        at: datetime,
    ) -> TariffRule | None:
        return (
            self.session.query(TariffRule)
            .filter(
                TariffRule.person_type == person_type,
                TariffRule.transaction_type == transaction_type,
                TariffRule.direction == direction,
                TariffRule.valid_from <= at,
            )
            .order_by(TariffRule.valid_from.desc())
            .first()
        )
