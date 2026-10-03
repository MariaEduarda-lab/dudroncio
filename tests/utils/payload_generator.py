from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_client_payload(cnpj: str = None, email: str = None, representative_email: str = None) -> dict:
        """Cadastro PJ valido; o representante tem CPF e e-mail novos."""
        if cnpj is None:
            cnpj = RandomGenerator.generate_cnpj()
        if email is None:
            email = f"financeiro.{uuid4()}@exemplo.com.br"
        if representative_email is None:
            representative_email = f"representante.{uuid4()}@exemplo.com.br"

        return {
            "person_type": "PJ",
            "document_number": cnpj,
            "legal_name": "Empresa Exemplo Tecnologia Ltda",
            "trade_name": "Empresa Exemplo",
            "primary_activity": "Desenvolvimento de software",
            "monthly_income_cents": 5000000,
            "email": email,
            "phone_number": "+5511999999999",
            "address": PayloadGenerator.create_address_payload(),
            "legal_representative": {
                "cpf": RandomGenerator.generate_cpf(),
                "full_name": "Maria da Silva",
                "birthdate": "1990-05-17",
                "email": representative_email,
                "phone_number": "+5511988888888",
                "role": "SOCIA_ADMINISTRADORA",
                "password": "senha-forte-123",
            },
        }

    @staticmethod
    def create_pf_client_payload(cpf: str = None, email: str = None) -> dict:
        """Cadastro PF valido, de uma pessoa maior de idade."""
        if cpf is None:
            cpf = RandomGenerator.generate_cpf()
        if email is None:
            email = f"pessoa.{uuid4()}@exemplo.com.br"

        return {
            "person_type": "PF",
            "document_number": cpf,
            "full_name": "Ana Souza",
            "birthdate": "1995-08-21",
            "password": "senha-forte-123",
            "monthly_income_cents": 750000,
            "email": email,
            "phone_number": "+5511977777777",
            "address": PayloadGenerator.create_address_payload(),
        }

    @staticmethod
    def create_address_payload() -> dict:
        return {
            "street": "Avenida Paulista",
            "number": "1000",
            "complement": "10 andar",
            "neighborhood": "Bela Vista",
            "city": "Sao Paulo",
            "state": "SP",
            "postal_code": "01310100",
            "country": "BR",
        }

    @staticmethod
    def create_account_status_payload(status: str, reason: str = None) -> dict:
        if reason is None:
            reason = f"Motivo do teste para {status}"
        return {"status": status, "reason": reason}

    @staticmethod
    def create_incoming_ted_payload(
        account: dict, amount_cents: int = 30000, external_id: str = None, payer_bank_code: str = "001"
    ) -> dict:
        """O aviso que o Banco Central manda quando chega uma TED de outro banco.

        `account` e a conta de destino como o GET /accounts devolve.
        """
        if external_id is None:
            external_id = f"TED-{uuid4()}"

        return {
            "external_id": external_id,
            "amount_cents": amount_cents,
            "recipient": {
                "branch": account["branch"],
                "account_number": account["account_number"],
                "check_digit": account["check_digit"],
            },
            "payer": {
                "name": "Carlos Pereira",
                "document": "52998224725",
                "bank_code": payer_bank_code,
                "branch": "1234",
                "account_number": "0098765",
            },
        }
