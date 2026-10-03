from copy import deepcopy
from datetime import date

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import ClientDTO
from errors import (
    DuplicatedClientEmail,
    DuplicatedCnpj,
    DuplicatedRepresentativeCpf,
    IneligibleCnpjStatus,
    InvalidCnpj,
    InvalidRepresentativeBirthdate,
    InvalidRepresentativeCpf,
    NotFoundClient,
)
from repositories import ClientRepository
from utils.document_number import is_valid_cnpj, is_valid_cpf, only_document_characters
from utils.password import hash_password


class ClientController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)

    def create(self, raw_client_data: dict) -> dict:
        client_data = self._normalize(raw_client_data)
        representative = client_data["legal_representative"]

        if not is_valid_cnpj(client_data["cnpj"]):
            raise InvalidCnpj(raw_client_data["cnpj"])

        if not is_valid_cpf(representative["cpf"]):
            raise InvalidRepresentativeCpf(raw_client_data["legal_representative"]["cpf"])

        representative["birthdate"] = self._valid_adult_birthdate(representative["birthdate"])

        if client_data["cnpj_status"] != "ACTIVE":
            raise IneligibleCnpjStatus(client_data["cnpj_status"])

        if self.client_repository.get_by_cnpj(client_data["cnpj"]) is not None:
            raise DuplicatedCnpj(client_data["cnpj"])

        self._check_email_is_available(client_data["email"])
        if representative["email"] != client_data["email"]:
            self._check_email_is_available(representative["email"])

        if self.client_repository.get_representative_by_cpf(representative["cpf"]) is not None:
            raise DuplicatedRepresentativeCpf(representative["cpf"])

        password_hash = hash_password(representative.pop("password"))
        client = self.client_repository.create(client_data, password_hash)

        try:
            self.session.flush()
            response = ClientDTO.only_key(client)
            self.session.commit()
        except IntegrityError as exception:
            self.session.rollback()
            self._raise_integrity_conflict(exception, client_data)

        return response

    def get_by_key(self, client_key: str) -> dict:
        client = self.client_repository.get_by_key(client_key)
        if client is None:
            raise NotFoundClient(client_key)
        return ClientDTO.obj_to_dict(client)

    def _normalize(self, raw_client_data: dict) -> dict:
        client_data = deepcopy(raw_client_data)
        client_data["cnpj"] = only_document_characters(client_data["cnpj"])
        client_data["email"] = client_data["email"].strip().lower()
        client_data["cnpj_status"] = client_data["cnpj_status"].upper()

        representative = client_data["legal_representative"]
        representative["cpf"] = only_document_characters(representative["cpf"])
        representative["email"] = representative["email"].strip().lower()
        return client_data

    def _check_email_is_available(self, email: str) -> None:
        if self.client_repository.get_by_email(email) is not None:
            raise DuplicatedClientEmail(email)
        if self.client_repository.get_representative_by_email(email) is not None:
            raise DuplicatedClientEmail(email)

    def _valid_adult_birthdate(self, raw_birthdate: str) -> date:
        try:
            birthdate = date.fromisoformat(raw_birthdate)
        except ValueError:
            raise InvalidRepresentativeBirthdate(raw_birthdate)

        today = date.today()
        age = today.year - birthdate.year
        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age -= 1

        if age < 18:
            raise InvalidRepresentativeBirthdate(raw_birthdate)
        return birthdate

    def _raise_integrity_conflict(self, exception: IntegrityError, client_data: dict) -> None:
        constraint_name = getattr(getattr(exception.orig, "diag", None), "constraint_name", "")
        representative = client_data["legal_representative"]

        if constraint_name == "uq_client_cnpj":
            raise DuplicatedCnpj(client_data["cnpj"])
        if constraint_name == "uq_client_email":
            raise DuplicatedClientEmail(client_data["email"])
        if constraint_name == "uq_legal_representative_email":
            raise DuplicatedClientEmail(representative["email"])
        if constraint_name == "uq_legal_representative_cpf":
            raise DuplicatedRepresentativeCpf(representative["cpf"])
        raise exception
