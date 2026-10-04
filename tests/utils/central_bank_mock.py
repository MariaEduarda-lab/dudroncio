from os import environ

import requests


def _mockserver_url() -> str:
    host = environ.get("SERVER_LOCALHOST", "0.0.0.0")
    port = environ.get("MOCKSERVER_PORT", "1080")
    return f"http://{host}:{port}/mockserver"


class CentralBankMock:
    """O teste no papel do Banco Central: diz ao Mockserver como responder.

    Cada expectativa casa so com o pedido que tem o campo informado (a
    chave Pix ou o numero da conta, sempre novos em cada teste), entao um
    teste nao responde pelo outro.
    """

    @staticmethod
    def answer_pix(pix_key: str, status: int, body: dict = None, delay_seconds: int = 0, times: int = None) -> None:
        CentralBankMock._expect("/pix", {"pix_key": pix_key}, status, body, delay_seconds, times)

    @staticmethod
    def answer_ted(account_number: str, status: int, body: dict = None, delay_seconds: int = 0, times: int = None) -> None:
        CentralBankMock._expect("/ted", {"recipient": {"account_number": account_number}}, status, body, delay_seconds, times)

    @staticmethod
    def pix_calls(pix_key: str) -> int:
        return CentralBankMock._count("/pix", {"pix_key": pix_key})

    @staticmethod
    def ted_calls(account_number: str) -> int:
        return CentralBankMock._count("/ted", {"recipient": {"account_number": account_number}})

    @staticmethod
    def confirmation(name: str = "Carlos Pereira", document: str = "52998224725", bank_code: str = "237") -> dict:
        """Resposta de envio confirmado, com os dados do recebedor no outro banco."""
        return {
            "status": "CONFIRMED",
            "recipient": {
                "name": name,
                "document": document,
                "bank_code": bank_code,
                "branch": "4321",
                "account_number": "0012345-6",
            },
        }

    @staticmethod
    def _request_matcher(path: str, fields: dict) -> dict:
        return {
            "method": "POST",
            "path": path,
            "body": {"type": "JSON", "json": fields, "matchType": "ONLY_MATCHING_FIELDS"},
        }

    @staticmethod
    def _expect(path: str, fields: dict, status: int, body: dict, delay_seconds: int, times: int) -> None:
        expectation = {
            "httpRequest": CentralBankMock._request_matcher(path, fields),
            "httpResponse": {
                "statusCode": status,
                "headers": {"Content-Type": ["application/json"]},
                "body": {"type": "JSON", "json": body or {}},
                "delay": {"timeUnit": "SECONDS", "value": delay_seconds},
            },
        }
        if times is not None:
            expectation["times"] = {"remainingTimes": times}
        response = requests.put(f"{_mockserver_url()}/expectation", json=expectation, timeout=5)
        assert response.status_code == 201, response.text

    @staticmethod
    def _count(path: str, fields: dict) -> int:
        response = requests.put(
            f"{_mockserver_url()}/retrieve?type=REQUESTS&format=JSON",
            json=CentralBankMock._request_matcher(path, fields),
            timeout=5,
        )
        assert response.status_code == 200, response.text
        return len(response.json())
