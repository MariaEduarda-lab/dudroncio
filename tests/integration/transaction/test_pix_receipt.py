from uuid import uuid4

import pytest

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator


# Pix que chega de outro banco, avisado pelo Banco Central (fake). O teste
# faz o papel do Banco Central. A conta e encontrada pela chave Pix: o
# documento (CPF da PF, CNPJ da PJ) ou o e-mail do cadastro (CLI-12).


def create_client_with_account(client_payload: dict) -> dict:
    status, client = RequestGenerator.POST_client(client_payload)
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


def only_digits(document: str) -> str:
    return "".join(character for character in document if character.isdigit())


class TestPixReceipt:
    def test_credits_pf_account_by_cpf(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        payload = PayloadGenerator.create_incoming_pix_payload(only_digits(cpf), amount_cents=15000)

        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(payload)
        assert status == 201
        assert set(transaction) == {
            "transaction_key",
            "type",
            "direction",
            "amount_cents",
            "fee_cents",
            "account_key",
            "pix_key",
            "payer",
            "created_at",
        }
        assert transaction["type"] == "PIX"
        assert transaction["direction"] == "IN"
        assert transaction["amount_cents"] == 15000
        assert transaction["fee_cents"] == 0
        assert transaction["account_key"] == account["account_key"]
        assert transaction["pix_key"] == only_digits(cpf)
        assert transaction["payer"] == payload["payer"]
        assert balance_of(account) == 15000

    def test_cpf_key_with_mask_finds_the_same_account(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))

        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(cpf)
        )
        assert status == 201
        assert transaction["account_key"] == account["account_key"]
        assert transaction["pix_key"] == only_digits(cpf)

    def test_credits_pj_account_by_cnpj(self):
        cnpj = RandomGenerator.generate_cnpj()
        account = create_client_with_account(PayloadGenerator.create_client_payload(cnpj=cnpj))

        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(cnpj, amount_cents=20000)
        )
        assert status == 201
        assert transaction["account_key"] == account["account_key"]
        assert balance_of(account) == 20000

    def test_credits_pj_account_by_alphanumeric_cnpj_in_lowercase(self):
        cnpj = RandomGenerator.generate_alphanumeric_cnpj()
        account = create_client_with_account(PayloadGenerator.create_client_payload(cnpj=cnpj))

        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(cnpj.lower())
        )
        assert status == 201
        assert transaction["account_key"] == account["account_key"]
        assert transaction["pix_key"] == cnpj

    def test_credits_account_by_email_ignoring_case(self):
        email = f"ana.{uuid4()}@exemplo.com.br"
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(email=email))

        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(email.upper())
        )
        assert status == 201
        assert transaction["account_key"] == account["account_key"]
        assert transaction["pix_key"] == email
        assert balance_of(account) == 15000

    def test_credits_pj_account_by_company_email(self):
        email = f"financeiro.{uuid4()}@exemplo.com.br"
        account = create_client_with_account(PayloadGenerator.create_client_payload(email=email))

        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(email)
        )
        assert status == 201
        assert transaction["account_key"] == account["account_key"]

    def test_repeated_notice_credits_only_once(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        payload = PayloadGenerator.create_incoming_pix_payload(only_digits(cpf))
        _, first = RequestGenerator.POST_webhook_central_bank_pix(payload)

        status, second = RequestGenerator.POST_webhook_central_bank_pix(payload)
        assert status == 200
        assert second == first
        assert balance_of(account) == 15000

    def test_repeated_notice_with_key_written_differently_is_the_same_pix(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        payload = PayloadGenerator.create_incoming_pix_payload(only_digits(cpf))
        _, first = RequestGenerator.POST_webhook_central_bank_pix(payload)

        status, second = RequestGenerator.POST_webhook_central_bank_pix({**payload, "pix_key": cpf})
        assert status == 200
        assert second == first
        assert balance_of(account) == 15000

    def test_refuses_same_external_id_with_different_content(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        payload = PayloadGenerator.create_incoming_pix_payload(only_digits(cpf), amount_cents=15000)
        RequestGenerator.POST_webhook_central_bank_pix(payload)

        status, response = RequestGenerator.POST_webhook_central_bank_pix({**payload, "amount_cents": 99999})
        assert status == 422
        assert response["code"] == "QIT004002"
        assert balance_of(account) == 15000

    def test_refuses_same_external_id_to_another_key(self):
        first_cpf = RandomGenerator.generate_cpf()
        first_account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=first_cpf))
        second_cpf = RandomGenerator.generate_cpf()
        second_account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=second_cpf))
        payload = PayloadGenerator.create_incoming_pix_payload(only_digits(first_cpf))
        RequestGenerator.POST_webhook_central_bank_pix(payload)

        status, response = RequestGenerator.POST_webhook_central_bank_pix(
            {**payload, "pix_key": only_digits(second_cpf)}
        )
        assert status == 422
        assert response["code"] == "QIT004002"
        assert balance_of(first_account) == 15000
        assert balance_of(second_account) == 0

    def test_same_external_id_from_another_bank_is_another_pix(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        external_id = f"E{uuid4().hex}"
        RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(only_digits(cpf), external_id=external_id, payer_bank_code="001")
        )

        status, _ = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(only_digits(cpf), external_id=external_id, payer_bank_code="237")
        )
        assert status == 201
        assert balance_of(account) == 30000

    def test_ted_and_pix_with_same_external_id_do_not_collide(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        external_id = f"E{uuid4().hex}"
        RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(account, amount_cents=30000, external_id=external_id)
        )

        status, _ = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(only_digits(cpf), external_id=external_id)
        )
        assert status == 201
        assert balance_of(account) == 45000

    def test_refuses_unknown_key(self):
        status, response = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(f"ninguem.{uuid4()}@exemplo.com.br")
        )
        assert status == 404
        assert response["code"] == "QIT004004"

    def test_representative_cpf_is_not_a_pix_key(self):
        payload = PayloadGenerator.create_client_payload()
        create_client_with_account(payload)

        status, response = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(only_digits(payload["legal_representative"]["cpf"]))
        )
        assert status == 404
        assert response["code"] == "QIT004004"

    def test_representative_email_is_not_a_pix_key(self):
        payload = PayloadGenerator.create_client_payload()
        create_client_with_account(payload)

        status, response = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(payload["legal_representative"]["email"])
        )
        assert status == 404
        assert response["code"] == "QIT004004"

    def test_refuses_client_without_account(self):
        cpf = RandomGenerator.generate_cpf()
        status, _ = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        assert status == 201

        status, response = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(only_digits(cpf))
        )
        assert status == 404
        assert response["code"] == "QIT004004"

    def test_refuses_blocked_account_without_spending_external_id(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        RequestGenerator.PATCH_account(account["account_key"], PayloadGenerator.create_account_status_payload("BLOCKED"))
        payload = PayloadGenerator.create_incoming_pix_payload(only_digits(cpf))

        status, response = RequestGenerator.POST_webhook_central_bank_pix(payload)
        assert status == 422
        assert response["code"] == "QIT004003"
        assert balance_of(account) == 0

        RequestGenerator.PATCH_account(account["account_key"], PayloadGenerator.create_account_status_payload("ACTIVE"))
        status, _ = RequestGenerator.POST_webhook_central_bank_pix(payload)
        assert status == 201
        assert balance_of(account) == 15000

    def test_refuses_closed_account(self):
        cpf = RandomGenerator.generate_cpf()
        account = create_client_with_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))
        RequestGenerator.PATCH_account(account["account_key"], PayloadGenerator.create_account_status_payload("CLOSED"))

        status, response = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(only_digits(cpf))
        )
        assert status == 422
        assert response["code"] == "QIT004003"


VALID_PAYLOAD = PayloadGenerator.create_incoming_pix_payload("ana@exemplo.com.br")


class TestPixReceiptValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            {**VALID_PAYLOAD, "amount_cents": 0},
            {**VALID_PAYLOAD, "amount_cents": 100000000001},
            {**VALID_PAYLOAD, "amount_cents": 10.5},
            {**VALID_PAYLOAD, "pix_key": ""},
            {**VALID_PAYLOAD, "pix_key": "x" * 256},
            {**VALID_PAYLOAD, "external_id": ""},
            {key: value for key, value in VALID_PAYLOAD.items() if key != "pix_key"},
            {**VALID_PAYLOAD, "recipient": {"branch": "0001", "account_number": "12345678", "check_digit": "1"}},
            {**VALID_PAYLOAD, "fee_cents": 0},
        ],
        ids=[
            "zero",
            "above_one_billion",
            "float",
            "empty_key",
            "long_key",
            "empty_external_id",
            "missing_key",
            "ted_recipient",
            "extra_field",
        ],
    )
    def test_refuses_invalid_notice(self, payload):
        status, response = RequestGenerator.POST_webhook_central_bank_pix(payload)
        assert status == 400
        assert response["code"] == "QIT000001"
