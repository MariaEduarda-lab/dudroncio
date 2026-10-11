from controllers.base_controller import BaseController
from controllers.creation_services import AccountCreator
from dtos import AccountDTO
from errors import AccountWithBalanceCannotBeClosed, ForbiddenAccountStatusTransition, NotFoundAccount, NotFoundClient
from models import Account
from repositories import AccountRepository, ClientRepository

ALLOWED_TRANSITIONS = {
    Account.ACTIVE: {Account.BLOCKED, Account.CLOSED},
    Account.BLOCKED: {Account.ACTIVE, Account.CLOSED},
}


class AccountController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.client_repository = ClientRepository(self.context)
        self.creator = AccountCreator(self.context)

    def create(self, client_key: str) -> dict:
        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise NotFoundClient(client_key)
        account = self.creator.create(client)
        response = AccountDTO.only_key(account)
        self.session.commit()
        return response

    def get_by_key(self, account_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)
        if account is None:
            raise NotFoundAccount(account_key)
        return AccountDTO.obj_to_dict(account)

    def update_status(self, account_key: str, new_status: str, reason: str) -> dict:
        account = self.account_repository.get_by_key_for_update(account_key)
        if account is None:
            raise NotFoundAccount(account_key)
        if account.status == new_status:
            response = AccountDTO.obj_to_dict(account)
            self.session.rollback()
            return response
        if new_status not in ALLOWED_TRANSITIONS.get(account.status, set()):
            raise ForbiddenAccountStatusTransition(account.status, new_status)
        if new_status == Account.CLOSED and account.balance_cents != 0:
            raise AccountWithBalanceCannotBeClosed()
        self.account_repository.update_status(account, new_status, reason)
        self.session.flush()
        # updated_at e mantido pelo trigger do banco; releia a linha sem dar
        # ao runtime permissao para escrever essa coluna diretamente.
        self.session.refresh(account)
        response = AccountDTO.obj_to_dict(account)
        self.session.commit()
        return response
