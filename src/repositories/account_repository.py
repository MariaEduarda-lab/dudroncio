from uuid import UUID, uuid4

from sqlalchemy import update
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

    def get_by_number(self, branch: str, account_number: str, check_digit: str) -> Account | None:
        return (
            self.session.query(Account)
            .filter(
                Account.branch == branch,
                Account.account_number == account_number,
                Account.check_digit == check_digit,
            )
            .first()
        )

    def credit(self, account_id: int, amount_cents: int) -> int | None:
        """Soma ao saldo num unico UPDATE e devolve o saldo que ficou.

        Nunca "le o saldo, calcula e grava": dois creditos simultaneos
        fariam um sobrescrever o outro (SAL-10). O status e conferido no
        mesmo UPDATE, com a linha travada: None quer dizer que a conta
        nao esta ativa (TRA-25).
        """
        return self.session.execute(
            update(Account)
            .where(Account.id == account_id, Account.status == Account.ACTIVE)
            .values(balance_cents=Account.balance_cents + amount_cents)
            .returning(Account.balance_cents)
        ).scalar_one_or_none()

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
