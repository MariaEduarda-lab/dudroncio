from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    @staticmethod
    def POST_client(client_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/clients",
            payload=client_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_client(client_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/clients/{client_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_account(client_key: str, account_payload: dict = None) -> BaseConnectorResponse:
        if account_payload is None:
            account_payload = {}
        response = ClientRequisition.send(
            "POST",
            f"/clients/{client_key}/accounts",
            payload=account_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_account(account_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/accounts/{account_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PATCH_account(account_key: str, account_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PATCH",
            f"/accounts/{account_key}",
            payload=account_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_webhook_central_bank_ted(ted_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/webhook/central_bank/teds",
            payload=ted_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_webhook_central_bank_pix(pix_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/webhook/central_bank/pix",
            payload=pix_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_transaction(account_key: str, transaction_payload: dict, idempotency_key: str = None) -> BaseConnectorResponse:
        """Envio de Pix ou TED. Sem idempotency_key, o cabecalho nao vai."""
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        response = ClientRequisition.send(
            "POST",
            f"/accounts/{account_key}/transactions",
            payload=transaction_payload,
            headers=headers,
        )
        return response.response_status, response.response_json
