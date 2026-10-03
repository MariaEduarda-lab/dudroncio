from uuid import uuid4

from sqlalchemy.orm import joinedload

from database import Context
from models import Account, Client


class AccountRepository:
    """Persistencia da conta; as regras de abertura ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, client: Client, account_number: str, check_digit: str) -> Account:
        account = Account(
            account_key=str(uuid4()),
            client=client,
            account_number=account_number,
            check_digit=check_digit,
            balance_cents=0,
        )
        self.session.add(account)
        return account

    def get_by_key(self, account_key: str) -> Account | None:
        return (
            self.session.query(Account)
            .options(joinedload(Account.client, innerjoin=True))
            .filter(Account.account_key == account_key)
            .first()
        )
