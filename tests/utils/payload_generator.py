from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_client_payload(cnpj: str = None, email: str = None, representative_email: str = None) -> dict:
        if cnpj is None:
            cnpj = RandomGenerator.generate_cnpj()
        if email is None:
            email = f"financeiro.{uuid4()}@exemplo.com.br"
        if representative_email is None:
            representative_email = f"representante.{uuid4()}@exemplo.com.br"

        return {
            "cnpj": cnpj,
            "legal_name": "Empresa Exemplo Tecnologia Ltda",
            "trade_name": "Empresa Exemplo",
            "client_type": "PJ",
            "cnpj_status": "ACTIVE",
            "primary_activity": "Desenvolvimento de software",
            "monthly_revenue_cents": 5000000,
            "email": email,
            "phone_number": "+5511999999999",
            "address": {
                "street": "Avenida Paulista",
                "number": "1000",
                "complement": "10 andar",
                "neighborhood": "Bela Vista",
                "city": "Sao Paulo",
                "state": "SP",
                "postal_code": "01310100",
                "country": "BR",
            },
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
    def create_sample_entity_payload(
        hello: str = None,
        name: str = None,
        email: str = None,
        document_number: str = None,
        birthdate: str = None,
    ) -> dict:
        """Um cadastro valido, com qualquer campo trocado a pedido.

        Sem argumento nenhum o payload sai aleatorio no que precisa ser
        unico (e-mail e CPF), pra que dois cadastros seguidos nao batam
        na regra de duplicidade. Quem testa FILTRO precisa do contrario
        disso: um valor conhecido, pra poder procurar por ele depois.
        """
        if hello is None:
            hello = "world"

        if name is None:
            name = "Maria da Silva"

        if email is None:
            email = f"maria.silva.{uuid4()}@exemplo.com.br"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        if birthdate is None:
            birthdate = "1990-05-17"

        payload = {
            "hello": hello,
            "name": name,
            "email": email,
            "document_number": document_number,
            "birthdate": birthdate,
        }
        return payload

    @staticmethod
    def create_new_status_payload(new_status: str = None) -> dict:
        payload = {"status": new_status}
        return payload
