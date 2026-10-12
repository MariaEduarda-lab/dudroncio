from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from connectors import CnpjRegistryConnector
from errors import (
    ClientAlreadyHasAccount, DuplicatedClientEmail, DuplicatedCnpj, DuplicatedCpf,
    DuplicatedRepresentativeCpf, IneligibleCnpjStatus, InternalError, InvalidBirthdate,
    InvalidCnpj, InvalidCpf, InvalidRepresentativeBirthdate, InvalidRepresentativeCpf,
)
from models import Account, Client
from repositories import AccountRepository, ClientRepository
from utils.account_number import account_check_digit, generate_account_number
from utils.document_number import is_valid_cnpj, is_valid_cpf, only_document_characters
from utils.password import hash_password

ADULT_AGE = 18
ACCOUNT_NUMBER_ATTEMPTS = 5
BRAZIL_TIMEZONE = ZoneInfo("America/Sao_Paulo")
EMAIL_CONSTRAINTS = {"pk_registered_email", "uq_client_email", "uq_legal_representative_email"}


class ClientCreator:
    """Valida e prepara um cliente sem decidir commit ou rollback."""

    def __init__(self, context, logger) -> None:
        self.repository = ClientRepository(context)
        self.cnpj_registry_connector = CnpjRegistryConnector()
        self.logger = logger

    def create(self, raw_client_data: dict) -> tuple[Client, dict]:
        client_data = self._normalize(raw_client_data)
        client = self._create_person(client_data) if client_data["person_type"] == Client.PF else self._create_company(client_data)
        return client, client_data

    def _create_person(self, client_data: dict) -> Client:
        if not is_valid_cpf(client_data["document_number"]):
            raise InvalidCpf()
        birthdate = self._adult_birthdate(client_data["birthdate"])
        if birthdate is None:
            raise InvalidBirthdate(client_data["birthdate"])
        client_data["birthdate"] = birthdate
        if self.repository.get_by_document(client_data["document_number"]) is not None:
            raise DuplicatedCpf()
        self._check_email_is_available(client_data["email"])
        return self.repository.create_person(client_data, hash_password(client_data.pop("password")))

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
        if self.repository.get_by_document(client_data["document_number"]) is not None:
            raise DuplicatedCnpj()
        if representative["email"] == client_data["email"]:
            raise DuplicatedClientEmail()
        self._check_email_is_available(client_data["email"])
        self._check_email_is_available(representative["email"])
        if self.repository.get_representative_by_cpf(representative["cpf"]) is not None:
            raise DuplicatedRepresentativeCpf()
        return self.repository.create_company(client_data, hash_password(representative.pop("password")))

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
        if self.repository.get_by_email(email) is not None or self.repository.get_representative_by_email(email) is not None:
            raise DuplicatedClientEmail()

    @staticmethod
    def _adult_birthdate(raw_birthdate: str) -> date | None:
        try:
            birthdate = date.fromisoformat(raw_birthdate)
        except ValueError:
            return None
        today = datetime.now(BRAZIL_TIMEZONE).date()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return birthdate if age >= ADULT_AGE else None

    def raise_integrity_conflict(self, exception: IntegrityError, client_data: dict) -> None:
        constraint_name = getattr(getattr(exception.orig, "diag", None), "constraint_name", None)
        if constraint_name == "uq_client_document":
            raise DuplicatedCpf() if client_data["person_type"] == Client.PF else DuplicatedCnpj()
        if constraint_name in EMAIL_CONSTRAINTS:
            raise DuplicatedClientEmail()
        if constraint_name == "uq_legal_representative_cpf":
            raise DuplicatedRepresentativeCpf()
        self.logger.error(f"IntegrityError inesperado no cadastro de cliente: constraint={constraint_name}")
        raise InternalError() from None


class AccountCreator:
    """Prepara e ativa uma conta sem decidir o commit da unidade de trabalho."""

    def __init__(self, context) -> None:
        self.repository = AccountRepository(context)

    def create(self, client: Client) -> Account:
        if client.account is not None:
            raise ClientAlreadyHasAccount()
        for _ in range(ACCOUNT_NUMBER_ATTEMPTS):
            account_number = generate_account_number()
            try:
                with self.repository.session.begin_nested():
                    account = self.repository.create(client, account_number, account_check_digit(account_number))
                    self.repository.session.flush()
            except IntegrityError as exception:
                constraint_name = getattr(getattr(exception.orig, "diag", None), "constraint_name", "")
                if constraint_name == "uq_account_number":
                    continue
                if constraint_name == "uq_account_client":
                    raise ClientAlreadyHasAccount()
                raise
            self.repository.update_status(account, Account.ACTIVE, None)
            self.repository.session.flush()
            return account
        raise RuntimeError("Nao foi possivel sortear um numero de conta livre.")
