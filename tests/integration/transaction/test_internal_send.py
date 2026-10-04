from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator


# Envio de Pix e TED entre duas contas do nosso banco: o dinheiro muda de
# conta aqui dentro, sem chamar o Banco Central. Quem envia paga a tarifa
# (PJ fora da cota); quem recebe recebe o valor cheio. Por enquanto a
# tarifa nao entra em conta nenhuma (a conta do banco esta adiada).

PIX_FEE = 99
TED_FEE = 499


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


def create_pf_account(email: str = None) -> dict:
    return create_account(PayloadGenerator.create_pf_client_payload(email=email))


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


def pix_to(recipient_email: str, amount_cents: int = 10000) -> dict:
    return PayloadGenerator.create_pix_send_payload(recipient_email, amount_cents)


def send(account: dict, payload: dict, idempotency_key: str = None):
    return RequestGenerator.POST_transaction(account["account_key"], payload, idempotency_key or new_key())


class TestInternalPix:
    def test_moves_money_between_our_clients_by_email(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)

        status, transaction = send(sender, pix_to(email, 10000))
        assert status == 201
        assert set(transaction) == {
            "transaction_key",
            "type",
            "amount_cents",
            "fee_cents",
            "account_key",
            "pix_key",
            "recipient",
            "created_at",
        }
        assert transaction["type"] == "PIX_OUT"
        assert transaction["amount_cents"] == 10000
        assert transaction["fee_cents"] == 0
        assert transaction["account_key"] == sender["account_key"]
        assert transaction["pix_key"] == email
        assert transaction["recipient"]["bank_code"] == "999"
        assert transaction["recipient"]["name"] == "Ana Souza"
        assert balance_of(sender) == 40000
        assert balance_of(recipient) == 10000

    def test_recipient_cpf_is_masked_in_the_response(self):
        sender = create_pf_account()
        fund(sender, 50000)
        cpf = RandomGenerator.generate_cpf()
        create_account(PayloadGenerator.create_pf_client_payload(cpf=cpf))

        status, transaction = send(sender, pix_to(cpf))
        assert status == 201
        assert transaction["pix_key"] == "".join(c for c in cpf if c.isdigit())
        assert transaction["recipient"]["document"] == f"***.***.***-{cpf[-2:]}"

    def test_moves_money_by_cnpj_key(self):
        sender = create_pf_account()
        fund(sender, 50000)
        cnpj = RandomGenerator.generate_cnpj()
        recipient = create_account(PayloadGenerator.create_client_payload(cnpj=cnpj))

        status, _ = send(sender, pix_to(cnpj, 20000))
        assert status == 201
        assert balance_of(recipient) == 20000

    def test_refuses_unknown_pix_key(self):
        sender = create_pf_account()
        fund(sender, 50000)

        status, response = send(sender, pix_to(f"ninguem.{uuid4()}@exemplo.com.br"))
        assert status == 404
        assert response["code"] == "QIT004004"
        assert balance_of(sender) == 50000

    def test_refuses_sending_to_own_account(self):
        email = f"ana.{uuid4()}@exemplo.com.br"
        sender = create_pf_account(email=email)
        fund(sender, 50000)

        status, response = send(sender, pix_to(email))
        assert status == 422
        assert response["code"] == "QIT004007"
        assert balance_of(sender) == 50000


class TestInternalTed:
    def test_moves_money_by_branch_and_account(self):
        sender = create_pf_account()
        fund(sender, 50000)
        recipient = create_pf_account()

        status, transaction = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 30000))
        assert status == 201
        assert set(transaction) == {
            "transaction_key",
            "type",
            "amount_cents",
            "fee_cents",
            "account_key",
            "recipient",
            "created_at",
        }
        assert transaction["type"] == "TED_OUT"
        assert transaction["recipient"]["bank_code"] == "999"
        assert transaction["recipient"]["branch"] == recipient["branch"]
        assert balance_of(sender) == 20000
        assert balance_of(recipient) == 30000

    def test_refuses_unknown_account_in_our_bank(self):
        sender = create_pf_account()
        fund(sender, 50000)
        unknown = {"branch": "0001", "account_number": "00000000", "check_digit": "0"}

        status, response = send(sender, PayloadGenerator.create_ted_send_payload(unknown))
        assert status == 404
        assert response["code"] == "QIT004001"
        assert balance_of(sender) == 50000

    def test_refuses_wrong_check_digit(self):
        sender = create_pf_account()
        fund(sender, 50000)
        recipient = create_pf_account()
        wrong_digit = str((int(recipient["check_digit"]) + 1) % 10)

        status, response = send(
            sender, PayloadGenerator.create_ted_send_payload({**recipient, "check_digit": wrong_digit})
        )
        assert status == 404
        assert response["code"] == "QIT004001"


class TestBalance:
    def test_refuses_without_enough_balance_and_changes_nothing(self):
        sender = create_pf_account()
        fund(sender, 5000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)

        status, response = send(sender, pix_to(email, 5001))
        assert status == 422
        assert response["code"] == "QIT004006"
        assert balance_of(sender) == 5000
        assert balance_of(recipient) == 0

    def test_sends_exactly_the_whole_balance(self):
        sender = create_pf_account()
        fund(sender, 5000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        create_pf_account(email=email)

        status, _ = send(sender, pix_to(email, 5000))
        assert status == 201
        assert balance_of(sender) == 0

    def test_refused_send_does_not_spend_the_idempotency_key(self):
        sender = create_pf_account()
        fund(sender, 5000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)
        key = new_key()

        status, _ = send(sender, pix_to(email, 8000), key)
        assert status == 422

        fund(sender, 3000)
        status, _ = send(sender, pix_to(email, 8000), key)
        assert status == 201
        assert balance_of(sender) == 0
        assert balance_of(recipient) == 8000


class TestAccountStatus:
    def test_refuses_unknown_sender_account(self):
        status, response = RequestGenerator.POST_transaction(str(uuid4()), pix_to("ana@exemplo.com.br"), new_key())
        assert status == 404
        assert response["code"] == "QIT003001"

    def test_refuses_blocked_sender(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        create_pf_account(email=email)
        RequestGenerator.PATCH_account(sender["account_key"], PayloadGenerator.create_account_status_payload("BLOCKED"))

        status, response = send(sender, pix_to(email))
        assert status == 422
        assert response["code"] == "QIT004003"
        assert balance_of(sender) == 50000

    def test_refuses_blocked_recipient(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)
        RequestGenerator.PATCH_account(
            recipient["account_key"], PayloadGenerator.create_account_status_payload("BLOCKED")
        )

        status, response = send(sender, pix_to(email))
        assert status == 422
        assert response["code"] == "QIT004003"
        assert balance_of(sender) == 50000
        assert balance_of(recipient) == 0

    def test_refuses_closed_recipient(self):
        sender = create_pf_account()
        fund(sender, 50000)
        recipient = create_pf_account()
        RequestGenerator.PATCH_account(recipient["account_key"], PayloadGenerator.create_account_status_payload("CLOSED"))

        status, response = send(sender, PayloadGenerator.create_ted_send_payload(recipient))
        assert status == 422
        assert response["code"] == "QIT004003"
        assert balance_of(sender) == 50000


class TestFee:
    def test_pf_never_pays(self):
        sender = create_pf_account()
        fund(sender, 100000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        create_pf_account(email=email)

        fees = [send(sender, pix_to(email, 100))[1]["fee_cents"] for _ in range(22)]
        assert fees == [0] * 22
        assert balance_of(sender) == 100000 - 22 * 100

    def test_pj_pays_from_the_21st_pix_and_recipient_gets_the_full_amount(self):
        sender = create_pj_account()
        fund(sender, 100000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)

        fees = [send(sender, pix_to(email, 100))[1]["fee_cents"] for _ in range(22)]
        assert fees == [0] * 20 + [PIX_FEE, PIX_FEE]
        assert balance_of(sender) == 100000 - 22 * 100 - 2 * PIX_FEE
        assert balance_of(recipient) == 22 * 100

    def test_pj_pays_from_the_3rd_ted(self):
        sender = create_pj_account()
        fund(sender, 100000)
        recipient = create_pf_account()

        fees = [send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))[1]["fee_cents"] for _ in range(3)]
        assert fees == [0, 0, TED_FEE]
        assert balance_of(sender) == 100000 - 3 * 1000 - TED_FEE
        assert balance_of(recipient) == 3000

    def test_pix_and_ted_quotas_are_separate(self):
        sender = create_pj_account()
        fund(sender, 100000)
        recipient = create_pf_account()

        for _ in range(2):
            assert send(sender, PayloadGenerator.create_ted_send_payload(recipient, 100))[1]["fee_cents"] == 0
        status, transaction = send(sender, PayloadGenerator.create_pix_send_payload(recipient_email(recipient), 100))
        assert status == 201
        assert transaction["fee_cents"] == 0

    def test_refuses_when_balance_covers_the_amount_but_not_the_fee(self):
        sender = create_pj_account()
        fund(sender, 2000 + 100)
        recipient = create_pf_account()
        for _ in range(2):
            send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))

        status, response = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 100))
        assert status == 422
        assert response["code"] == "QIT004006"
        assert balance_of(sender) == 100

    def test_refused_send_does_not_spend_quota(self):
        sender = create_pj_account()
        fund(sender, 2000)
        recipient = create_pf_account()
        send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))

        status, _ = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 999999))
        assert status == 422

        status, transaction = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))
        assert status == 201
        assert transaction["fee_cents"] == 0


class TestIdempotency:
    def test_repeated_request_returns_the_same_transaction_and_moves_money_once(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)
        key = new_key()

        status, first = send(sender, pix_to(email, 10000), key)
        assert status == 201
        status, second = send(sender, pix_to(email, 10000), key)
        assert status == 200
        assert second == first
        assert balance_of(sender) == 40000
        assert balance_of(recipient) == 10000

    def test_repeated_request_with_key_written_differently_is_the_same_request(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        create_pf_account(email=email)
        key = new_key()
        send(sender, pix_to(email, 10000), key)

        status, _ = send(sender, pix_to(email.upper(), 10000), key)
        assert status == 200
        assert balance_of(sender) == 40000

    def test_same_key_with_different_request_is_refused(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        create_pf_account(email=email)
        key = new_key()
        send(sender, pix_to(email, 10000), key)

        status, response = send(sender, pix_to(email, 20000), key)
        assert status == 422
        assert response["code"] == "QIT004002"
        assert balance_of(sender) == 40000

    def test_same_key_in_another_account_is_another_request(self):
        first_sender = create_pf_account()
        second_sender = create_pf_account()
        fund(first_sender, 50000)
        fund(second_sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)
        key = new_key()

        assert send(first_sender, pix_to(email, 10000), key)[0] == 201
        assert send(second_sender, pix_to(email, 10000), key)[0] == 201
        assert balance_of(recipient) == 20000

    def test_repeated_pj_request_does_not_charge_the_fee_again(self):
        sender = create_pj_account()
        fund(sender, 100000)
        recipient = create_pf_account()
        for _ in range(2):
            send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000))
        key = new_key()

        _, first = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000), key)
        status, second = send(sender, PayloadGenerator.create_ted_send_payload(recipient, 1000), key)
        assert status == 200
        assert second["fee_cents"] == first["fee_cents"] == TED_FEE
        assert balance_of(sender) == 100000 - 3 * 1000 - TED_FEE

    def test_double_click_creates_a_single_transaction(self):
        sender = create_pf_account()
        fund(sender, 50000)
        email = f"ana.{uuid4()}@exemplo.com.br"
        recipient = create_pf_account(email=email)
        key = new_key()

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: send(sender, pix_to(email, 10000), key), range(5)))

        assert sorted(status for status, _ in results) == [200, 200, 200, 200, 201]
        assert len({response["transaction_key"] for _, response in results}) == 1
        assert balance_of(sender) == 40000
        assert balance_of(recipient) == 10000

    @pytest.mark.parametrize("key", [None, "", "x" * 65, "chave com espaco"], ids=["missing", "empty", "long", "space"])
    def test_refuses_missing_or_invalid_idempotency_key(self, key):
        sender = create_pf_account()
        fund(sender, 50000)

        status, response = RequestGenerator.POST_transaction(sender["account_key"], pix_to("ana@exemplo.com.br"), key)
        assert status == 400
        assert response["code"] == "QIT004005"
        assert balance_of(sender) == 50000


def recipient_email(account: dict) -> str:
    """E-mail do dono da conta, para usar como chave Pix."""
    status, client = RequestGenerator.GET_client(account["client_key"])
    assert status == 200
    return client["email"]


VALID_PIX = PayloadGenerator.create_pix_send_payload("ana@exemplo.com.br")
VALID_TED = PayloadGenerator.create_ted_send_payload({"branch": "0001", "account_number": "12345678", "check_digit": "1"})


class TestSendValidation:
    @pytest.mark.parametrize(
        "payload",
        [
            {**VALID_PIX, "amount_cents": 0},
            {**VALID_PIX, "amount_cents": -100},
            {**VALID_PIX, "amount_cents": 100000000001},
            {**VALID_PIX, "amount_cents": 10.5},
            {**VALID_PIX, "amount_cents": "100"},
            {**VALID_PIX, "type": "BOLETO"},
            {**VALID_PIX, "pix_key": ""},
            {**VALID_PIX, "fee_cents": 0},
            {key: value for key, value in VALID_PIX.items() if key != "pix_key"},
            {**VALID_PIX, "recipient": VALID_TED["recipient"]},
            {**VALID_TED, "pix_key": "ana@exemplo.com.br"},
            {key: value for key, value in VALID_TED.items() if key != "recipient"},
            {**VALID_TED, "recipient": {**VALID_TED["recipient"], "bank_code": "99"}},
            {**VALID_TED, "recipient": {**VALID_TED["recipient"], "check_digit": "X"}},
        ],
        ids=[
            "zero",
            "negative",
            "above_one_billion",
            "float",
            "string_amount",
            "unknown_type",
            "empty_pix_key",
            "client_informs_fee",
            "pix_without_key",
            "pix_with_ted_recipient",
            "ted_with_pix_key",
            "ted_without_recipient",
            "short_bank_code",
            "letter_check_digit",
        ],
    )
    def test_refuses_invalid_request(self, payload):
        sender = create_pf_account()

        status, response = send(sender, payload)
        assert status == 400
        assert response["code"] == "QIT000001"
