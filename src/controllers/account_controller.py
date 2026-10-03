from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import AccountDTO
from errors import ClientAlreadyHasAccount, NotFoundAccount, NotFoundClient
from repositories import AccountRepository, ClientRepository
from utils.account_number import account_check_digit, generate_account_number

ACCOUNT_NUMBER_ATTEMPTS = 5


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

            response = AccountDTO.only_key(account)
            self.session.commit()
            return response

        raise Exception("Nao foi possivel sortear um numero de conta livre.")

    def get_by_key(self, account_key: str) -> dict:
        account = self.account_repository.get_by_key(account_key)
        if account is None:
            raise NotFoundAccount(account_key)
        return AccountDTO.obj_to_dict(account)
