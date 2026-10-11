from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from controllers.creation_services import AccountCreator, ClientCreator
from dtos import AccountDTO, ClientDTO


class OnboardingController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_creator = ClientCreator(self.context, self.logger)
        self.account_creator = AccountCreator(self.context)

    def create(self, raw_client_data: dict) -> dict:
        client, client_data = self.client_creator.create(raw_client_data)
        try:
            self.session.flush()
            account = self.account_creator.create(client)
            response = {
                "client": ClientDTO.obj_to_dict(client),
                "account": AccountDTO.obj_to_dict(account),
            }
            self.session.commit()
            return response
        except IntegrityError as exception:
            self.session.rollback()
            self.client_creator.raise_integrity_conflict(exception, client_data)
        except Exception:
            self.session.rollback()
            raise
