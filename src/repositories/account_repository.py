from uuid import UUID, uuid4

from sqlalchemy.orm import joinedload

from database import Context
from models import Account, Client


class AccountRepository:
    """Persistencia da conta; as regras de abertura ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, client: Client, account_number: str, check_digit: str) -> Account:
        account = Account(
            account_key=uuid4(),
            client=client,
            account_number=account_number,
            check_digit=check_digit,
            balance_cents=0,
            status=Account.CREATED,
        )
        self.session.add(account)
        return account

    def update_status(self, account: Account, status: str, reason: str | None) -> None:
        account.status = status
        account.status_reason = reason

    def get_by_key(self, account_key: str) -> Account | None:
        return self._query_by_key(account_key).first()

    def get_by_key_for_update(self, account_key: str) -> Account | None:
        """Busca travando a linha ate o fim da transacao.

        Duas mudancas simultaneas na mesma conta (um bloqueio e um
        encerramento, ou o encerramento e um debito) esperam uma pela
        outra, e a segunda decide olhando o estado ja atualizado.
        """
        return self._query_by_key(account_key).with_for_update(of=Account).first()

    def _query_by_key(self, account_key: str):
        # Chave em formato invalido nao existe: vira "nao encontrado", e nao
        # um erro do banco ao comparar texto com UUID.
        try:
            parsed_key = UUID(account_key)
        except ValueError:
            parsed_key = None

        return (
            self.session.query(Account)
            .options(joinedload(Account.client, innerjoin=True))
            .filter(Account.account_key == parsed_key)
        )
