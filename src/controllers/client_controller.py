from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from connectors import CnpjRegistryConnector
from controllers.base_controller import BaseController
from dtos import ClientDTO
from errors import (
    DuplicatedClientEmail,
    DuplicatedCnpj,
    DuplicatedCpf,
    DuplicatedRepresentativeCpf,
    IneligibleCnpjStatus,
    InternalError,
    InvalidBirthdate,
    InvalidCnpj,
    InvalidCpf,
    InvalidRepresentativeBirthdate,
    InvalidRepresentativeCpf,
    NotFoundClient,
)
from models import Client
from repositories import ClientRepository
from utils.document_number import is_valid_cnpj, is_valid_cpf, only_document_characters
from utils.password import hash_password

ADULT_AGE = 18

# A maioridade conta no calendario de Brasilia, e nao no do servidor (UTC):
# entre 21h e meia-noite o UTC ja esta no dia seguinte, e quem faz 18 anos
# "amanha" seria aceito hoje.
BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")

EMAIL_CONSTRAINTS = {"pk_registered_email", "uq_client_email", "uq_legal_representative_email"}


class ClientController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.client_repository = ClientRepository(self.context)
        self.cnpj_registry_connector = CnpjRegistryConnector()

    def create(self, raw_client_data: dict) -> dict:
        client_data = self._normalize(raw_client_data)

        if client_data["person_type"] == Client.PF:
            client = self._create_person(client_data)
        else:
            client = self._create_company(client_data)

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

    def _create_person(self, client_data: dict) -> Client:
        if not is_valid_cpf(client_data["document_number"]):
            raise InvalidCpf()

        birthdate = self._adult_birthdate(client_data["birthdate"])
        if birthdate is None:
            raise InvalidBirthdate(client_data["birthdate"])
        client_data["birthdate"] = birthdate

        if self.client_repository.get_by_document(client_data["document_number"]) is not None:
            raise DuplicatedCpf()

        self._check_email_is_available(client_data["email"])

        password_hash = hash_password(client_data.pop("password"))
        return self.client_repository.create_person(client_data, password_hash)

    def _create_company(self, client_data: dict) -> Client:
        representative = client_data["legal_representative"]

        if not is_valid_cnpj(client_data["document_number"]):
            raise InvalidCnpj()

        if not is_valid_cpf(representative["cpf"]):
            raise InvalidRepresentativeCpf()

        birthdate = self._adult_birthdate(representative["birthdate"])
        if birthdate is None:
            raise InvalidRepresentativeBirthdate(representative["birthdate"])
        representative["birthdate"] = birthdate

        client_data["cnpj_status"] = self.cnpj_registry_connector.get_cnpj_status(client_data["document_number"])
        if client_data["cnpj_status"] != "ACTIVE":
            raise IneligibleCnpjStatus(client_data["cnpj_status"])

        if self.client_repository.get_by_document(client_data["document_number"]) is not None:
            raise DuplicatedCnpj()

        # CLI-06 sem excecao: nem a empresa e o proprio representante
        # dividem um e-mail.
        if representative["email"] == client_data["email"]:
            raise DuplicatedClientEmail()
        self._check_email_is_available(client_data["email"])
        self._check_email_is_available(representative["email"])

        # O CPF de um titular PF pode representar uma PJ (decisao de 04/10);
        # so dois representantes com o mesmo CPF e que nao pode.
        if self.client_repository.get_representative_by_cpf(representative["cpf"]) is not None:
            raise DuplicatedRepresentativeCpf()

        password_hash = hash_password(representative.pop("password"))
        return self.client_repository.create_company(client_data, password_hash)

    def _normalize(self, raw_client_data: dict) -> dict:
        client_data = deepcopy(raw_client_data)
        client_data["document_number"] = only_document_characters(client_data["document_number"])
        client_data["email"] = client_data["email"].strip().lower()

        representative = client_data.get("legal_representative")
        if representative is not None:
            representative["cpf"] = only_document_characters(representative["cpf"])
            representative["email"] = representative["email"].strip().lower()
        return client_data

    def _check_email_is_available(self, email: str) -> None:
        # Checagem antecipada, para a resposta comum. Quem garante CLI-06
        # sob cadastros simultaneos e a tabela registered_email no banco.
        if self.client_repository.get_by_email(email) is not None:
            raise DuplicatedClientEmail()
        if self.client_repository.get_representative_by_email(email) is not None:
            raise DuplicatedClientEmail()

    def _adult_birthdate(self, raw_birthdate: str) -> date | None:
        """Data de nascimento de alguem maior de idade, ou None."""
        try:
            birthdate = date.fromisoformat(raw_birthdate)
        except ValueError:
            return None

        today = datetime.now(BRAZIL_TIMEZONE).date()
        age = today.year - birthdate.year
        if (today.month, today.day) < (birthdate.month, birthdate.day):
            age -= 1

        if age < ADULT_AGE:
            return None
        return birthdate

    def _raise_integrity_conflict(self, exception: IntegrityError, client_data: dict) -> None:
        constraint_name = getattr(getattr(exception.orig, "diag", None), "constraint_name", None)

        if constraint_name == "uq_client_document":
            if client_data["person_type"] == Client.PF:
                raise DuplicatedCpf()
            raise DuplicatedCnpj()
        if constraint_name in EMAIL_CONSTRAINTS:
            raise DuplicatedClientEmail()
        if constraint_name == "uq_legal_representative_cpf":
            raise DuplicatedRepresentativeCpf()

        # O texto do IntegrityError traz os valores da linha (CPF, hash da
        # senha). No log vai so o nome da constraint.
        self.logger.error(f"IntegrityError inesperado no cadastro de cliente: constraint={constraint_name}")
        raise InternalError() from None
