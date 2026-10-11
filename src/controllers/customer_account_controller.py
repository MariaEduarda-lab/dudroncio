from controllers.base_controller import BaseController
from errors import CustomerAccountNotFound
from models import Client
from repositories import AccountRepository, ClientRepository
from utils.access_token import AuthenticatedPrincipal


class CustomerAccountController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)
        self.account_repository = AccountRepository(self.context)

    def resolve(self, principal: AuthenticatedPrincipal):
        if principal.kind == "PF":
            client = self.client_repository.get_by_key(principal.subject)
            if client is None or client.person_type != Client.PF:
                raise CustomerAccountNotFound()
        else:
            representative = self.client_repository.get_representative_by_key(principal.subject)
            if representative is None:
                raise CustomerAccountNotFound()
            client = representative.client

        account = self.account_repository.get_by_client_id(client.id)
        if account is None:
            raise CustomerAccountNotFound()
        return account
