from concurrent.futures import ThreadPoolExecutor

from tests.utils import PayloadGenerator, RequestGenerator

UNKNOWN_KEY = "00000000-0000-0000-0000-000000000000"


def create_client() -> str:
    status, response = RequestGenerator.POST_client(PayloadGenerator.create_client_payload())
    assert status == 201
    return response["client_key"]


def create_account() -> str:
    status, response = RequestGenerator.POST_account(create_client())
    assert status == 201
    return response["account_key"]


def modulo_11_check_digit(number: str) -> str:
    total = sum(int(digit) * weight for digit, weight in zip(reversed(number), range(2, 10)))
    digit = 11 - total % 11
    return "0" if digit >= 10 else str(digit)


class TestAccountOpening:
    def test_opens_active_account_with_zero_balance(self):
        client_key = create_client()

        status, response = RequestGenerator.POST_account(client_key)
        assert status == 201
        assert set(response) == {"account_key"}

        status, account = RequestGenerator.GET_account(response["account_key"])
        assert status == 200
        assert set(account) == {
            "account_key",
            "client_key",
            "branch",
            "account_number",
            "check_digit",
            "balance_cents",
            "status",
            "status_reason",
            "created_at",
            "updated_at",
        }
        assert account["account_key"] == response["account_key"]
        assert account["client_key"] == client_key
        assert account["branch"] == "0001"
        assert len(account["account_number"]) == 8
        assert account["account_number"].isdigit()
        assert account["check_digit"] == modulo_11_check_digit(account["account_number"])
        assert account["balance_cents"] == 0
        assert account["status"] == "ACTIVE"

    def test_refuses_unknown_client(self):
        status, response = RequestGenerator.POST_account(UNKNOWN_KEY)
        assert status == 404
        assert response["code"] == "QIT002001"

    def test_refuses_unexpected_body_field(self):
        status, response = RequestGenerator.POST_account(create_client(), {"balance_cents": 1000})
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_second_account_for_same_client(self):
        client_key = create_client()
        status, _ = RequestGenerator.POST_account(client_key)
        assert status == 201

        status, response = RequestGenerator.POST_account(client_key)
        assert status == 409
        assert response["code"] == "QIT003002"

    def test_concurrent_openings_create_only_one_account(self):
        client_key = create_client()

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: RequestGenerator.POST_account(client_key), range(5)))

        statuses = sorted(status for status, _ in results)
        assert statuses == [201, 409, 409, 409, 409]


class TestAccountQuery:
    def test_account_not_found(self):
        status, response = RequestGenerator.GET_account(UNKNOWN_KEY)
        assert status == 404
        assert response["code"] == "QIT003001"

    def test_key_in_invalid_format_is_not_found(self):
        status, response = RequestGenerator.GET_account("nao-e-uma-chave")
        assert status == 404
        assert response["code"] == "QIT003001"

    def test_key_in_uppercase_finds_the_same_account(self):
        account_key = create_account()

        status, account = RequestGenerator.GET_account(account_key.upper())
        assert status == 200
        assert account["account_key"] == account_key


class TestAccountStatusChange:
    def test_blocks_active_account_with_reason(self):
        account_key = create_account()
        _, before = RequestGenerator.GET_account(account_key)

        payload = PayloadGenerator.create_account_status_payload("BLOCKED", "Suspeita de fraude")
        status, account = RequestGenerator.PATCH_account(account_key, payload)
        assert status == 200
        assert account["status"] == "BLOCKED"
        assert account["status_reason"] == "Suspeita de fraude"
        assert account["updated_at"] > before["updated_at"]

    def test_reactivates_blocked_account(self):
        account_key = create_account()
        RequestGenerator.PATCH_account(account_key, PayloadGenerator.create_account_status_payload("BLOCKED"))

        payload = PayloadGenerator.create_account_status_payload("ACTIVE", "Analise concluida")
        status, account = RequestGenerator.PATCH_account(account_key, payload)
        assert status == 200
        assert account["status"] == "ACTIVE"
        assert account["status_reason"] == "Analise concluida"

    def test_repeating_current_status_changes_nothing(self):
        account_key = create_account()
        payload = PayloadGenerator.create_account_status_payload("BLOCKED")
        _, first = RequestGenerator.PATCH_account(account_key, payload)

        status, second = RequestGenerator.PATCH_account(account_key, payload)
        assert status == 200
        assert second == first

    def test_closes_account_with_zero_balance(self):
        account_key = create_account()

        payload = PayloadGenerator.create_account_status_payload("CLOSED", "Pedido do cliente")
        status, account = RequestGenerator.PATCH_account(account_key, payload)
        assert status == 200
        assert account["status"] == "CLOSED"

    def test_closed_account_cannot_change_status(self):
        account_key = create_account()
        RequestGenerator.PATCH_account(account_key, PayloadGenerator.create_account_status_payload("CLOSED"))

        status, response = RequestGenerator.PATCH_account(
            account_key, PayloadGenerator.create_account_status_payload("ACTIVE")
        )
        assert status == 409
        assert response["code"] == "QIT003003"

    def test_refuses_created_as_target_status(self):
        status, response = RequestGenerator.PATCH_account(
            create_account(), PayloadGenerator.create_account_status_payload("CREATED")
        )
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_status_change_without_reason(self):
        status, response = RequestGenerator.PATCH_account(create_account(), {"status": "BLOCKED"})
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_status_change_of_unknown_account(self):
        status, response = RequestGenerator.PATCH_account(
            UNKNOWN_KEY, PayloadGenerator.create_account_status_payload("BLOCKED")
        )
        assert status == 404
        assert response["code"] == "QIT003001"
