import requests

from connectors.rest_connector import BaseConnectorResponse, RestConnector
from constants import CENTRAL_BANK_API_INTERNAL_TOKEN, CENTRAL_BANK_API_TIMEOUT, CENTRAL_BANK_API_URL


class CentralBankConnector(RestConnector):
    """Fala com o Banco Central (fake) nos envios para outro banco.

    O envio e sincrono (TRA-17): o nosso banco pergunta e espera a
    resposta por no maximo CENTRAL_BANK_API_TIMEOUT segundos. Quando nao
    ha resposta (tempo esgotado, conexao recusada), os metodos devolvem
    None em vez de levantar o erro do requests: para a regra de negocio,
    "nao respondeu" e uma resposta possivel, e ela manda recusar.
    """

    def __init__(self) -> None:
        super().__init__(
            class_name=__name__,
            base_url=CENTRAL_BANK_API_URL,
            timeout=CENTRAL_BANK_API_TIMEOUT,
            internal_token=CENTRAL_BANK_API_INTERNAL_TOKEN,
        )

    def send_pix(self, transaction_key: str, amount_cents: int, pix_key: str, payer: dict) -> BaseConnectorResponse | None:
        payload = {"transaction_key": transaction_key, "amount_cents": amount_cents, "pix_key": pix_key, "payer": payer}
        return self._send_or_none("/pix", payload)

    def send_ted(
        self, transaction_key: str, amount_cents: int, recipient: dict, payer: dict
    ) -> BaseConnectorResponse | None:
        payload = {"transaction_key": transaction_key, "amount_cents": amount_cents, "recipient": recipient, "payer": payer}
        return self._send_or_none("/ted", payload)

    def _send_or_none(self, endpoint: str, payload: dict) -> BaseConnectorResponse | None:
        try:
            return self.send(endpoint=endpoint, method="POST", payload=payload)
        except requests.RequestException as exception:
            self.logger.warning(f"Banco Central sem resposta em {endpoint}: {type(exception).__name__}")
            return None
