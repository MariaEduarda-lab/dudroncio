from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import AccountDTO
from errors import (
    AccountWithBalanceCannotBeClosed,
    ClientAlreadyHasAccount,
    ForbiddenAccountStatusTransition,
    NotFoundAccount,
    NotFoundClient,
)
from models import Account
from repositories import AccountRepository, ClientRepository
from utils.account_number import account_check_digit, generate_account_number

ACCOUNT_NUMBER_ATTEMPTS = 5

# Para onde cada status pode ir pelo PATCH. CLOSED nao aparece como
# origem: conta encerrada nao volta. CREATED so existe durante a abertura.
ALLOWED_TRANSITIONS = {
    Account.ACTIVE: {Account.BLOCKED, Account.CLOSED},
    Account.BLOCKED: {Account.ACTIVE, Account.CLOSED},
}


class AccountController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.client_repository = ClientRepository(self.context)

    def create(self, client_key: str) -> dict:
        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise NotFoundClient(client_key)

        if client.account is not None:
            raise ClientAlreadyHasAccount()

        for _ in range(ACCOUNT_NUMBER_ATTEMPTS):
            account_number = generate_account_number()
            try:
                # O savepoint deixa desfazer so esta tentativa se o numero
                # sorteado ja existir, sem perder o resto da transacao.
                with self.session.begin_nested():
                    account = self.account_repository.create(
                        client, account_number, account_check_digit(account_number)
                    )
                    self.session.flush()
            except IntegrityError as exception:
                constraint_name = getattr(getattr(exception.orig, "diag", None), "constraint_name", "")
                if constraint_name == "uq_account_number":
                    continue

                self.session.rollback()
                # Duas aberturas simultaneas passam pela checagem acima; quem
                # garante uma conta por cliente e o UNIQUE do banco.
                if constraint_name == "uq_account_client":
                    raise ClientAlreadyHasAccount()
                raise exception

            # A conta nasce CREATED e e ativada na mesma transacao: quem
            # consulta nunca a encontra pela metade.
            self.account_repository.update_status(account, Account.ACTIVE, None)
            self.session.flush()
            response = AccountDTO.only_key(account)
            self.session.commit()
            return response

        raise Exception("Nao foi possivel sortear um numero de conta livre.")

    def get_by_key(self, account_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)
        if account is None:
            raise NotFoundAccount(account_key)
        return AccountDTO.obj_to_dict(account)

    def update_status(self, account_key: str, new_status: str, reason: str) -> dict:
        account = self.account_repository.get_by_key_for_update(account_key)
        if account is None:
            raise NotFoundAccount(account_key)

        # Repetir o status atual nao e uma transicao: devolve a conta como
        # esta, sem gravar nada. E isso que torna o PATCH idempotente.
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
        response = AccountDTO.obj_to_dict(account)
        self.session.commit()
        return response
