from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from controllers.creation_services import ClientCreator
from dtos import ClientDTO
from errors import NotFoundClient
from repositories import ClientRepository


class ClientController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)
        self.creator = ClientCreator(self.context, self.logger)

    def create(self, raw_client_data: dict) -> dict:
        client, client_data = self.creator.create(raw_client_data)
        try:
            self.session.flush()
            response = ClientDTO.only_key(client)
            self.session.commit()
            return response
        except IntegrityError as exception:
            self.session.rollback()
            self.creator.raise_integrity_conflict(exception, client_data)

    def get_by_key(self, client_key: str) -> dict:
        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise NotFoundClient(client_key)
        return ClientDTO.obj_to_dict(client)
