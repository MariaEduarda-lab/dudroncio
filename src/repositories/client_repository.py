from uuid import UUID, uuid4

from sqlalchemy.orm import selectinload

from database import Context
from models import Client, LegalRepresentative
from utils.pix_key import is_email_key, normalize_pix_key


class ClientRepository:
    """Persistencia do cadastro; regras de elegibilidade ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create_person(self, client_data: dict, password_hash: str) -> Client:
        client = self._new_client(client_data, Client.PF)
        client.full_name = client_data["full_name"]
        client.birthdate = client_data["birthdate"]
        client.password_hash = password_hash
        self.session.add(client)
        return client

    def create_company(self, client_data: dict, representative_password_hash: str) -> Client:
        client = self._new_client(client_data, Client.PJ)
        client.legal_name = client_data["legal_name"]
        client.trade_name = client_data.get("trade_name")
        client.cnpj_status = client_data["cnpj_status"]
        client.primary_activity = client_data["primary_activity"]

        representative_data = client_data["legal_representative"]
        representative = LegalRepresentative(
            representative_key=uuid4(),
            cpf=representative_data["cpf"],
            full_name=representative_data["full_name"],
            birthdate=representative_data["birthdate"],
            email=representative_data["email"],
            phone_number=representative_data["phone_number"],
            role=representative_data["role"],
            password_hash=representative_password_hash,
        )
        client.legal_representatives.append(representative)
        self.session.add(client)
        return client

    def get_by_key(self, client_key: str) -> Client | None:
        # Chave em formato invalido nao existe: vira "nao encontrado", e nao
        # um erro do banco ao comparar texto com UUID.
        try:
            parsed_key = UUID(client_key)
        except ValueError:
            return None

        # Os representantes vem na mesma ida ao banco: o DTO nao consulta nada.
        return (
            self.session.query(Client)
            .options(selectinload(Client.legal_representatives))
            .filter(Client.client_key == parsed_key)
            .first()
        )

    def get_by_document(self, document_number: str) -> Client | None:
        return self.session.query(Client).filter(Client.document_number == document_number).first()

    def get_by_pix_key(self, pix_key: str) -> Client | None:
        """Cliente dono da chave Pix: o e-mail ou o documento do cadastro (CLI-12).

        Com "@" e e-mail; senao e documento, sem mascara e em maiusculas. Os
        dados do representante (CPF e e-mail) nao sao chave Pix: so a tabela
        de clientes e consultada.
        """
        return self.session.query(Client).filter(_pix_key_filter(normalize_pix_key(pix_key))).first()

    def get_by_email(self, email: str) -> Client | None:
        return self.session.query(Client).filter(Client.email == email).first()

    def get_representative_by_email(self, email: str) -> LegalRepresentative | None:
        return self.session.query(LegalRepresentative).filter(LegalRepresentative.email == email).first()

    def get_representative_by_cpf(self, cpf: str) -> LegalRepresentative | None:
        return self.session.query(LegalRepresentative).filter(LegalRepresentative.cpf == cpf).first()

    def _new_client(self, client_data: dict, person_type: str) -> Client:
        return Client(
            client_key=uuid4(),
            person_type=person_type,
            document_number=client_data["document_number"],
            monthly_income_cents=client_data["monthly_income_cents"],
            email=client_data["email"],
            phone_number=client_data["phone_number"],
            address=dict(client_data["address"]),
        )


def _pix_key_filter(pix_key: str):
    if is_email_key(pix_key):
        return Client.email == pix_key
    return Client.document_number == pix_key
