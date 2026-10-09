import random
from uuid import uuid4

from tests.utils import CentralBankMock, PayloadGenerator, RequestGenerator


# Envio de Pix e TED para outro banco. O nosso banco pergunta ao Banco
# Central (Mockserver) e espera a resposta por um tempo limitado (TRA-17):
# so debita e registra se ele confirmar. Recusa, falta de resposta ou
# resposta sem sentido: o pedido e recusado e nada muda (TRA-18).

TED_FEE = 499
CENTRAL_BANK_TIMEOUT_SECONDS = 5


def new_key() -> str:
    return str(uuid4())


def create_account(client_payload: dict) -> dict:
    status, client = RequestGenerator.POST_client(client_payload)
    assert status == 201
    status, response = RequestGenerator.POST_account(client["client_key"])
    assert status == 201
    status, account = RequestGenerator.GET_account(response["account_key"])
    assert status == 200
    return account


def create_pf_account() -> dict:
    return create_account(PayloadGenerator.create_pf_client_payload())


def create_pj_account() -> dict:
    return create_account(PayloadGenerator.create_client_payload())


def fund(account: dict, amount_cents: int) -> None:
    status, _ = RequestGenerator.POST_webhook_central_bank_ted(
        PayloadGenerator.create_incoming_ted_payload(account, amount_cents=amount_cents)
    )
    assert status == 201


def balance_of(account: dict) -> int:
    status, current = RequestGenerator.GET_account(account["account_key"])
    assert status == 200
    return current["balance_cents"]


def send(account: dict, payload: dict, idempotency_key: str = None):
    return RequestGenerator.POST_transaction(account["account_key"], payload, idempotency_key or new_key())


def external_pix_key() -> str:
    return f"carlos.{uuid4()}@outrobanco.com.br"


def external_account() -> dict:
    return {"branch": "4321", "account_number": f"{random.randrange(10**8):08d}", "check_digit": "7"}


def external_ted(account: dict, amount_cents: int = 10000) -> dict:
    return PayloadGenerator.create_ted_send_payload(account, amount_cents, bank_code="237")


class TestExternalPix:
    def test_sends_when_the_central_bank_confirms(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation(name="Carlos Pereira"))

        status, transaction = send(sender, PayloadGenerator.create_pix_send_payload(pix_key, 10000))
        assert status == 201
        assert transaction["type"] == "PIX"
        assert transaction["direction"] == "OUT"
        assert transaction["amount_cents"] == 10000
        assert transaction["fee_cents"] == 0
        assert transaction["pix_key"] == pix_key
        assert transaction["recipient"] == {
            "name": "Carlos Pereira",
            "document": "***.***.***-25",
            "bank_code": "237",
            "branch": "4321",
            "account_number": "0012345-6",
        }
        assert balance_of(sender) == 40000
        assert CentralBankMock.pix_calls(pix_key) == 1

    def test_key_unknown_to_the_central_bank_is_not_found(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 404)

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key))
        assert status == 404
        assert response["code"] == "QIT004004"
        assert balance_of(sender) == 50000
        assert CentralBankMock.pix_calls(pix_key) == 1

    def test_refused_by_the_central_bank_changes_nothing(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 422, {"reason": "RECIPIENT_ACCOUNT_CLOSED"})

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key))
        assert status == 422
        assert response["code"] == "QIT004008"
        assert balance_of(sender) == 50000

    def test_refusal_does_not_spend_the_idempotency_key(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 422, times=1)
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation())
        key = new_key()

        status, _ = send(sender, PayloadGenerator.create_pix_send_payload(pix_key, 10000), key)
        assert status == 422
        status, _ = send(sender, PayloadGenerator.create_pix_send_payload(pix_key, 10000), key)
        assert status == 201
        assert balance_of(sender) == 40000

    def test_central_bank_error_is_unavailable(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 500)

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key))
        assert status == 503
        assert response["code"] == "QIT004009"
        assert balance_of(sender) == 50000

    def test_confirmation_without_recipient_data_is_not_trusted(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 200, {"status": "CONFIRMED"})

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key))
        assert status == 503
        assert response["code"] == "QIT004009"
        assert balance_of(sender) == 50000

    def test_no_answer_in_time_is_unavailable_and_changes_nothing(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation(), delay_seconds=CENTRAL_BANK_TIMEOUT_SECONDS + 1)

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key))
        assert status == 503
        assert response["code"] == "QIT004009"
        assert balance_of(sender) == 50000

    def test_does_not_call_the_central_bank_without_balance(self):
        sender = create_pf_account()
        fund(sender, 5000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation())

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key, 5001))
        assert status == 422
        assert response["code"] == "QIT004006"
        assert CentralBankMock.pix_calls(pix_key) == 0

    def test_does_not_call_the_central_bank_from_a_blocked_account(self):
        sender = create_pf_account()
        fund(sender, 50000)
        RequestGenerator.PATCH_account(sender["account_key"], PayloadGenerator.create_account_status_payload("BLOCKED"))
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation())

        status, response = send(sender, PayloadGenerator.create_pix_send_payload(pix_key))
        assert status == 422
        assert response["code"] == "QIT004003"
        assert CentralBankMock.pix_calls(pix_key) == 0

    def test_repeated_request_calls_the_central_bank_once(self):
        sender = create_pf_account()
        fund(sender, 50000)
        pix_key = external_pix_key()
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation())
        key = new_key()

        status, first = send(sender, PayloadGenerator.create_pix_send_payload(pix_key, 10000), key)
        assert status == 201
        status, second = send(sender, PayloadGenerator.create_pix_send_payload(pix_key, 10000), key)
        assert status == 200
        assert second == first
        assert balance_of(sender) == 40000
        assert CentralBankMock.pix_calls(pix_key) == 1


class TestExternalTed:
    def test_sends_when_the_central_bank_confirms(self):
        sender = create_pf_account()
        fund(sender, 50000)
        account = external_account()
        CentralBankMock.answer_ted(account["account_number"], 200, CentralBankMock.confirmation(bank_code="237"))

        status, transaction = send(sender, external_ted(account, 30000))
        assert status == 201
        assert transaction["type"] == "TED"
        assert transaction["direction"] == "OUT"
        assert transaction["recipient"]["bank_code"] == "237"
        assert "pix_key" not in transaction
        assert balance_of(sender) == 20000
        assert CentralBankMock.ted_calls(account["account_number"]) == 1

    def test_unknown_account_in_the_other_bank_is_not_found(self):
        sender = create_pf_account()
        fund(sender, 50000)
        account = external_account()
        CentralBankMock.answer_ted(account["account_number"], 404)

        status, response = send(sender, external_ted(account))
        assert status == 404
        assert response["code"] == "QIT004001"
        assert balance_of(sender) == 50000
        assert CentralBankMock.ted_calls(account["account_number"]) == 1

    def test_refused_by_the_central_bank_changes_nothing(self):
        sender = create_pf_account()
        fund(sender, 50000)
        account = external_account()
        CentralBankMock.answer_ted(account["account_number"], 422)

        status, response = send(sender, external_ted(account))
        assert status == 422
        assert response["code"] == "QIT004008"
        assert balance_of(sender) == 50000

    def test_external_teds_count_for_the_pj_quota(self):
        sender = create_pj_account()
        fund(sender, 100000)
        recipient = create_pf_account()
        for _ in range(2):
            send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))
        account = external_account()
        CentralBankMock.answer_ted(account["account_number"], 200, CentralBankMock.confirmation())

        status, transaction = send(sender, external_ted(account, 1000))
        assert status == 201
        assert transaction["fee_cents"] == TED_FEE
        assert balance_of(sender) == 100000 - 3 * 1000 - TED_FEE

    def test_refused_external_ted_does_not_charge_fee_nor_spend_quota(self):
        sender = create_pj_account()
        fund(sender, 100000)
        recipient = create_pf_account()
        send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))
        account = external_account()
        CentralBankMock.answer_ted(account["account_number"], 422)

        status, _ = send(sender, external_ted(account, 1000))
        assert status == 422

        status, transaction = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))
        assert status == 201
        assert transaction["fee_cents"] == 0
        assert balance_of(sender) == 100000 - 2 * 1000
