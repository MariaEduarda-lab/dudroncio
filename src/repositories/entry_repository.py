from uuid import UUID

from sqlalchemy.orm import joinedload

from database import Context
from models import Account, Entry, Transaction


class EntryRepository:
    """Leitura dos lancamentos; eles so nascem dentro de uma transacao."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_key(self, entry_key: str) -> Entry | None:
        # Chave em formato invalido nao existe: vira "nao encontrado".
        try:
            parsed_key = UUID(entry_key)
        except ValueError:
            return None
        return self.session.query(Entry).filter(Entry.entry_key == parsed_key).first()

    def list_for_statement(self, account_id: int, before_entry_id: int | None, limit: int) -> list[Entry]:
        """Lancamentos da conta, do mais recente para o mais antigo.

        A pagina seguinte comeca abaixo do id da ultima linha vista, e nao
        num deslocamento: um lancamento novo entra no topo e nao empurra
        as linhas das paginas seguintes (EXT-05).
        """
        query = (
            self.session.query(Entry)
            .options(
                joinedload(Entry.transaction)
                .joinedload(Transaction.source_account)
                .joinedload(Account.client)
            )
            .filter(Entry.account_id == account_id)
        )
        if before_entry_id is not None:
            query = query.filter(Entry.id < before_entry_id)
        return query.order_by(Entry.id.desc()).limit(limit).all()
