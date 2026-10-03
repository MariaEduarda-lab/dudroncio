from concurrent.futures import ThreadPoolExecutor

from tests.utils import PayloadGenerator, RequestGenerator


def create_client() -> str:
    status, response = RequestGenerator.POST_client(PayloadGenerator.create_client_payload())
    assert status == 201
    return response["client_key"]


def modulo_11_check_digit(number: str) -> str:
    total = sum(int(digit) * weight for digit, weight in zip(reversed(number), range(2, 10)))
    digit = 11 - total % 11
    return "0" if digit >= 10 else str(digit)


class TestAccountOpening:
    def test_opens_account_with_zero_balance(self):
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
            "created_at",
        }
        assert account["account_key"] == response["account_key"]
        assert account["client_key"] == client_key
        assert account["branch"] == "0001"
        assert len(account["account_number"]) == 8
        assert account["account_number"].isdigit()
        assert account["check_digit"] == modulo_11_check_digit(account["account_number"])
        assert account["balance_cents"] == 0

    def test_refuses_unknown_client(self):
        status, response = RequestGenerator.POST_account("00000000-0000-0000-0000-000000000000")
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
        status, response = RequestGenerator.GET_account("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT003001"

