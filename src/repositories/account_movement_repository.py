from uuid import UUID

from sqlalchemy.orm import joinedload

from database import Context
from models import Account, AccountMovement, Transaction


class AccountMovementRepository:
    """Leitura dos movimentos imutáveis usados para formar o extrato."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_key(self, movement_key: str) -> AccountMovement | None:
        # Chave em formato invalido nao existe: vira "nao encontrado".
        try:
            parsed_key = UUID(movement_key)
        except ValueError:
            return None
        return (
            self.session.query(AccountMovement)
            .filter(AccountMovement.movement_key == parsed_key)
            .first()
        )

    def list_for_statement(
        self,
        account_id: int,
        before_movement_id: int | None,
        limit: int,
    ) -> list[AccountMovement]:
        """Movimentos da conta, do mais recente para o mais antigo.

        A pagina seguinte comeca abaixo do id da ultima linha vista, e nao
        num deslocamento: um movimento novo entra no topo e nao empurra as
        linhas das paginas seguintes (EXT-05).
        """
        query = (
            self.session.query(AccountMovement)
            .options(
                joinedload(AccountMovement.transaction)
                .joinedload(Transaction.source_account)
                .joinedload(Account.client)
            )
            .filter(AccountMovement.account_id == account_id)
        )
        if before_movement_id is not None:
            query = query.filter(AccountMovement.id < before_movement_id)
        return query.order_by(AccountMovement.id.desc()).limit(limit).all()
