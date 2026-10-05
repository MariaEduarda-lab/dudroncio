from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest


from tests.utils import PayloadGenerator, RequestGenerator


def create_account() -> dict:
    status, client = RequestGenerator.POST_client(PayloadGenerator.create_client_payload())
    assert status == 201
    status, response = RequestGenerator.POST_account(client["client_key"])
    assert status == 201
    status, account = RequestGenerator.GET_account(response["account_key"])
    assert status == 200
    return account


def balance_of(account: dict) -> int:
    status, current = RequestGenerator.GET_account(account["account_key"])
    assert status == 200
    return current["balance_cents"]


class TestTedReceipt:
    def test_credits_recipient_account(self):
        account = create_account()
        payload = PayloadGenerator.create_incoming_ted_payload(account, amount_cents=30000)

        status, transaction = RequestGenerator.POST_webhook_central_bank_ted(payload)
        assert status == 201
        assert set(transaction) == {
            "transaction_key",
            "type",
            "direction",
            "amount_cents",
            "fee_cents",
            "status",
            "status_reason",
            "account_key",
            "payer",
            "created_at",
            "updated_at",
            "completed_at",
        }
        assert transaction["type"] == "TED"
        assert transaction["direction"] == "IN"
        assert transaction["status"] == "COMPLETED"
        assert transaction["amount_cents"] == 30000
        assert transaction["fee_cents"] == 0
        assert transaction["account_key"] == account["account_key"]
        assert transaction["payer"] == payload["payer"]
        assert balance_of(account) == 30000

    def test_repeated_notice_credits_only_once(self):
        account = create_account()
        payload = PayloadGenerator.create_incoming_ted_payload(account, amount_cents=30000)
        _, first = RequestGenerator.POST_webhook_central_bank_ted(payload)

        status, second = RequestGenerator.POST_webhook_central_bank_ted(payload)
        assert status == 200
        assert second == first
        assert balance_of(account) == 30000

    def test_concurrent_repeated_notices_credit_only_once(self):
        account = create_account()
        payload = PayloadGenerator.create_incoming_ted_payload(account, amount_cents=30000)

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: RequestGenerator.POST_webhook_central_bank_ted(payload), range(5)))

        assert sorted(status for status, _ in results) == [200, 200, 200, 200, 201]
        assert len({response["transaction_key"] for _, response in results}) == 1
        assert balance_of(account) == 30000

    def test_concurrent_different_notices_all_credit(self):
        account = create_account()

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(
                executor.map(
                    lambda _: RequestGenerator.POST_webhook_central_bank_ted(
                        PayloadGenerator.create_incoming_ted_payload(account, amount_cents=100)
                    ),
                    range(10),
                )
            )

        assert [status for status, _ in results] == [201] * 10
        assert balance_of(account) == 1000

    def test_same_external_id_from_another_bank_is_another_ted(self):
        account = create_account()
        external_id = f"TED-{uuid4()}"
        RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(account, external_id=external_id, payer_bank_code="001")
        )

        status, _ = RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(account, external_id=external_id, payer_bank_code="237")
        )
        assert status == 201
        assert balance_of(account) == 60000

    def test_refuses_same_external_id_with_different_content(self):
        account = create_account()
        payload = PayloadGenerator.create_incoming_ted_payload(account, amount_cents=30000)
        RequestGenerator.POST_webhook_central_bank_ted(payload)

        status, response = RequestGenerator.POST_webhook_central_bank_ted({**payload, "amount_cents": 99999})
        assert status == 422
        assert response["code"] == "QIT004002"
        assert balance_of(account) == 30000

    def test_refuses_unknown_account(self):
        account = {"branch": "0001", "account_number": "00000000", "check_digit": "0"}

        status, response = RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(account)
        )
        assert status == 404
        assert response["code"] == "QIT004001"

    def test_refuses_wrong_check_digit(self):
        account = create_account()
        wrong_digit = str((int(account["check_digit"]) + 1) % 10)

        status, response = RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload({**account, "check_digit": wrong_digit})
        )
        assert status == 404
        assert response["code"] == "QIT004001"
        assert balance_of(account) == 0

    def test_refuses_blocked_account_without_spending_external_id(self):
        account = create_account()
        RequestGenerator.PATCH_account(
            account["account_key"], PayloadGenerator.create_account_status_payload("BLOCKED")
        )
        payload = PayloadGenerator.create_incoming_ted_payload(account, amount_cents=30000)

        status, response = RequestGenerator.POST_webhook_central_bank_ted(payload)
        assert status == 422
        assert response["code"] == "QIT004003"
        assert balance_of(account) == 0

        RequestGenerator.PATCH_account(
            account["account_key"], PayloadGenerator.create_account_status_payload("ACTIVE")
        )
        status, _ = RequestGenerator.POST_webhook_central_bank_ted(payload)
        assert status == 201
        assert balance_of(account) == 30000

    def test_refuses_closed_account(self):
        account = create_account()
        RequestGenerator.PATCH_account(account["account_key"], PayloadGenerator.create_account_status_payload("CLOSED"))

        status, response = RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(account)
        )
        assert status == 422
        assert response["code"] == "QIT004003"


def without(data: dict, *path: str) -> dict:
    """Copia do payload sem o campo indicado (aceita caminho aninhado)."""
    copy = deepcopy(data)
    target = copy
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    return copy


def replaced(data: dict, value, *path: str) -> dict:
    copy = deepcopy(data)
    target = copy
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return copy


VALID_ACCOUNT = {"branch": "0001", "account_number": "12345678", "check_digit": "1"}
VALID_PAYLOAD = PayloadGenerator.create_incoming_ted_payload(VALID_ACCOUNT)


class TestTedReceiptValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            replaced(VALID_PAYLOAD, 0, "amount_cents"),
            replaced(VALID_PAYLOAD, -100, "amount_cents"),
            replaced(VALID_PAYLOAD, 100000000001, "amount_cents"),
            replaced(VALID_PAYLOAD, 10.5, "amount_cents"),
            replaced(VALID_PAYLOAD, "100", "amount_cents"),
            replaced(VALID_PAYLOAD, "", "external_id"),
            replaced(VALID_PAYLOAD, "x" * 65, "external_id"),
            replaced(VALID_PAYLOAD, "", "payer", "name"),
            replaced(VALID_PAYLOAD, "123", "payer", "document"),
            replaced(VALID_PAYLOAD, "1", "payer", "bank_code"),
            replaced(VALID_PAYLOAD, "1234567", "recipient", "account_number"),
            replaced(VALID_PAYLOAD, "A", "recipient", "check_digit"),
            without(VALID_PAYLOAD, "payer", "name"),
            without(VALID_PAYLOAD, "recipient", "branch"),
            without(VALID_PAYLOAD, "external_id"),
            {**VALID_PAYLOAD, "fee_cents": 0},
        ],
        ids=[
            "zero",
            "negative",
            "above_one_billion",
            "float",
            "string_amount",
            "empty_external_id",
            "long_external_id",
            "empty_payer_name",
            "short_document",
            "short_bank_code",
            "short_account_number",
            "letter_check_digit",
            "missing_payer_name",
            "missing_branch",
            "missing_external_id",
            "extra_field",
        ],
    )
    def test_refuses_invalid_notice(self, payload):
        status, response = RequestGenerator.POST_webhook_central_bank_ted(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_accepts_amount_of_exactly_one_billion(self):
        account = create_account()

        status, _ = RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(account, amount_cents=100000000000)
        )
        assert status == 201
        assert balance_of(account) == 100000000000
