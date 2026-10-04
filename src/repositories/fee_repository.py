from datetime import datetime

from database import Context
from models import FeeRule


class FeeRepository:
    """Leitura da tabela de precos; a tabela so recebe linhas novas pelo database.sql."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_current_rule(self, person_type: str, transaction_type: str, at: datetime) -> FeeRule | None:
        """Regra vigente em `at`: a de maior valid_from que ja tinha comecado."""
        return (
            self.session.query(FeeRule)
            .filter(
                FeeRule.person_type == person_type,
                FeeRule.transaction_type == transaction_type,
                FeeRule.valid_from <= at,
            )
            .order_by(FeeRule.valid_from.desc())
            .first()
        )
