from uuid import uuid4

from database import Context
from models import Client, LegalRepresentative


class ClientRepository:
    """Persistencia do cadastro; regras de elegibilidade ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, client_data: dict, password_hash: str) -> Client:
        client = Client(
            client_key=str(uuid4()),
            cnpj=client_data["cnpj"],
            legal_name=client_data["legal_name"],
            trade_name=client_data.get("trade_name"),
            client_type=client_data["client_type"],
            cnpj_status=client_data["cnpj_status"],
            primary_activity=client_data["primary_activity"],
            monthly_revenue_cents=client_data["monthly_revenue_cents"],
            email=client_data["email"],
            phone_number=client_data["phone_number"],
            address=dict(client_data["address"]),
        )

        representative_data = client_data["legal_representative"]
        representative = LegalRepresentative(
            representative_key=str(uuid4()),
            cpf=representative_data["cpf"],
            full_name=representative_data["full_name"],
            birthdate=representative_data["birthdate"],
            email=representative_data["email"],
            phone_number=representative_data["phone_number"],
            role=representative_data["role"],
            password_hash=password_hash,
        )
        client.legal_representatives.append(representative)
        self.session.add(client)
        return client

    def get_by_key(self, client_key: str) -> Client | None:
        return self.session.query(Client).filter(Client.client_key == client_key).first()

    def get_by_cnpj(self, cnpj: str) -> Client | None:
        return self.session.query(Client).filter(Client.cnpj == cnpj).first()

    def get_by_email(self, email: str) -> Client | None:
        return self.session.query(Client).filter(Client.email == email).first()

    def get_representative_by_email(self, email: str) -> LegalRepresentative | None:
        return self.session.query(LegalRepresentative).filter(LegalRepresentative.email == email).first()

    def get_representative_by_cpf(self, cpf: str) -> LegalRepresentative | None:
        return self.session.query(LegalRepresentative).filter(LegalRepresentative.cpf == cpf).first()
