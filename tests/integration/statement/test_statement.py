from uuid import uuid4

import pytest

from tests.utils import CentralBankMock, PayloadGenerator, RequestGenerator


# Extrato (06-extrato.md): a leitura, em paginas, dos lancamentos da conta.
# Mais recente primeiro, tarifa numa linha separada do valor, e somando
# todas as linhas chega-se exatamente ao saldo.

PIX_FEE = 99
TED_FEE = 499
MOVEMENT_FIELDS = {
    "movement_key",
    "created_at",
    "direction",
    "movement_type",
    "description",
    "amount_cents",
    "balance_after_cents",
    "transaction_key",
    "counterparty_name",
}


def create_account(client_payload: dict) -> dict:
    status, client = RequestGenerator.POST_client(client_payload)
    assert status == 201
    status, response = RequestGenerator.POST_account(client["client_key"])
    assert status == 201
    status, account = RequestGenerator.GET_account(response["account_key"])
    assert status == 200
    return {**account, "email": client_payload["email"]}


def create_pf_account() -> dict:
    return create_account(PayloadGenerator.create_pf_client_payload())


def create_pj_account() -> dict:
    return create_account(PayloadGenerator.create_client_payload())


def receive_ted(account: dict, amount_cents: int) -> None:
    status, _ = RequestGenerator.POST_webhook_central_bank_ted(
        PayloadGenerator.create_incoming_ted_payload(account, amount_cents=amount_cents)
    )
    assert status == 201


def pix(sender: dict, pix_key: str, amount_cents: int):
    return RequestGenerator.POST_transaction(
        sender["account_key"], PayloadGenerator.create_pix_send_payload(pix_key, amount_cents), str(uuid4())
    )


def statement(account: dict, **query_params) -> dict:
    status, response = RequestGenerator.GET_statement(account["account_key"], query_params or None)
    assert status == 200
    return response


def all_entries(account: dict, limit: int = 3) -> list:
    """Percorre todas as paginas, da mais recente para a mais antiga."""
    entries, cursor = [], None
    while True:
        params = {"limit": limit} if cursor is None else {"limit": limit, "after": cursor}
        page = statement(account, **params)
        entries += page["movements"]
        cursor = page["next_cursor"]
        if cursor is None:
            return entries


def balance_of(account: dict) -> int:
    status, current = RequestGenerator.GET_account(account["account_key"])
    assert status == 200
    return current["balance_cents"]


class TestStatementLines:
    def test_new_account_has_an_empty_statement(self):
        account = create_pf_account()

        assert statement(account) == {"movements": [], "next_cursor": None}

    def test_received_ted_shows_who_paid(self):
        account = create_pf_account()
        receive_ted(account, 30000)

        [entry] = statement(account)["movements"]
        assert set(entry) == MOVEMENT_FIELDS
        assert entry["direction"] == "CREDIT"
        assert entry["movement_type"] == "PRINCIPAL"
        assert entry["description"] == "TED recebida de Carlos Pereira"
        assert entry["counterparty_name"] == "Carlos Pereira"
        assert entry["amount_cents"] == 30000
        assert entry["balance_after_cents"] == 30000
        assert entry["created_at"].endswith("-03:00")

    def test_received_pix_shows_who_paid(self):
        account = create_pf_account()
        status, transaction = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(account["email"], amount_cents=15000)
        )
        assert status == 201

        [entry] = statement(account)["movements"]
        assert entry["description"] == "Pix recebido de Carlos Pereira"
        assert entry["transaction_key"] == transaction["transaction_key"]

    def test_most_recent_first(self):
        account = create_pf_account()
        recipient = create_pf_account()
        receive_ted(account, 10000)
        pix(account, recipient["email"], 3000)
        receive_ted(account, 500)

        entries = statement(account)["movements"]
        assert [entry["amount_cents"] for entry in entries] == [500, 3000, 10000]
        assert [entry["direction"] for entry in entries] == ["CREDIT", "DEBIT", "CREDIT"]
        assert [entry["balance_after_cents"] for entry in entries] == [7500, 7000, 10000]

    def test_fee_is_a_separate_line_above_the_value(self):
        company = create_pj_account()
        recipient = create_pf_account()
        receive_ted(company, 100000)
        for _ in range(20):
            pix(company, recipient["email"], 100)

        status, transaction = pix(company, recipient["email"], 50000)
        assert status == 201

        fee, value = statement(company, limit=2)["movements"]
        assert fee["movement_type"] == "FEE"
        assert fee["direction"] == "DEBIT"
        assert fee["description"] == "Tarifa de Pix"
        assert fee["amount_cents"] == PIX_FEE
        assert fee["counterparty_name"] is None
        assert value["movement_type"] == "PRINCIPAL"
        assert value["direction"] == "DEBIT"
        assert value["description"] == "Pix para Ana Souza"
        assert value["amount_cents"] == 50000
        assert fee["transaction_key"] == value["transaction_key"] == transaction["transaction_key"]
        assert value["balance_after_cents"] == fee["balance_after_cents"] + PIX_FEE
        assert fee["balance_after_cents"] == balance_of(company)

    def test_free_send_is_a_single_line(self):
        person = create_pf_account()
        recipient = create_pf_account()
        receive_ted(person, 10000)
        pix(person, recipient["email"], 1000)

        entries = statement(person)["movements"]
        assert [entry["movement_type"] for entry in entries] == ["PRINCIPAL", "PRINCIPAL"]

    def test_internal_transfer_shows_each_side_the_other_name(self):
        company = create_pj_account()
        person = create_pf_account()
        receive_ted(company, 10000)
        pix(company, person["email"], 2500)

        [sent] = statement(company, limit=1)["movements"]
        [received] = statement(person)["movements"]
        assert sent["description"] == "Pix para Ana Souza"
        assert received["description"] == "Pix recebido de Empresa Exemplo Tecnologia Ltda"
        assert received["counterparty_name"] == "Empresa Exemplo Tecnologia Ltda"
        assert received["amount_cents"] == 2500
        assert sent["transaction_key"] == received["transaction_key"]

    def test_ted_sent_and_its_fee(self):
        company = create_pj_account()
        recipient = create_pf_account()
        receive_ted(company, 100000)
        ted = PayloadGenerator.create_ted_send_payload(recipient, 1000)
        for _ in range(3):
            RequestGenerator.POST_transaction(company["account_key"], ted, str(uuid4()))

        fee, value = statement(company, limit=2)["movements"]
        assert fee["description"] == "Tarifa de TED"
        assert fee["amount_cents"] == TED_FEE
        assert value["description"] == "TED para Ana Souza"

    def test_pix_to_another_bank_shows_the_name_given_by_the_central_bank(self):
        person = create_pf_account()
        receive_ted(person, 10000)
        pix_key = f"carlos.{uuid4()}@outrobanco.com.br"
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation(name="Carlos Lima"))
        pix(person, pix_key, 4000)

        [entry] = statement(person, limit=1)["movements"]
        assert entry["description"] == "Pix para Carlos Lima"
        assert entry["amount_cents"] == 4000
        assert entry["direction"] == "DEBIT"

    def test_refused_requests_do_not_appear(self):
        person = create_pf_account()
        recipient = create_pf_account()
        receive_ted(person, 1000)

        status, _ = pix(person, recipient["email"], 5000)
        assert status == 422

        assert len(statement(person)["movements"]) == 1


class TestStatementPages:
    def test_pages_have_at_most_the_limit_and_cover_everything_once(self):
        account = create_pf_account()
        for amount in [100, 200, 300, 400, 500]:
            receive_ted(account, amount)

        first = statement(account, limit=2)
        second = statement(account, limit=2, after=first["next_cursor"])
        third = statement(account, limit=2, after=second["next_cursor"])

        amounts = [[entry["amount_cents"] for entry in page["movements"]] for page in (first, second, third)]
        assert amounts == [[500, 400], [300, 200], [100]]
        assert third["next_cursor"] is None

    def test_default_page_has_50_lines(self):
        company = create_pj_account()
        recipient = create_pf_account()
        receive_ted(company, 100000)
        # 1 recebimento + 20 Pix gratis + 20 Pix pagos (valor e tarifa) = 61 linhas.
        for _ in range(40):
            pix(company, recipient["email"], 10)

        page = statement(company)
        assert len(page["movements"]) == 50
        assert page["next_cursor"] == page["movements"][-1]["movement_key"]
        assert len(statement(company, after=page["next_cursor"])["movements"]) == 11

    def test_new_movement_does_not_shift_the_next_page(self):
        account = create_pf_account()
        for amount in [100, 200, 300, 400]:
            receive_ted(account, amount)
        first = statement(account, limit=2)

        receive_ted(account, 999)

        second = statement(account, limit=2, after=first["next_cursor"])
        assert [entry["amount_cents"] for entry in second["movements"]] == [200, 100]

    def test_cursor_from_another_account_is_refused(self):
        account = create_pf_account()
        other = create_pf_account()
        receive_ted(other, 100)
        other_entry = statement(other)["movements"][0]["movement_key"]

        status, response = RequestGenerator.GET_statement(account["account_key"], {"after": other_entry})
        assert status == 422
        assert response["code"] == "QIT006001"

    @pytest.mark.parametrize("cursor", [str(uuid4()), "nao-e-uuid"], ids=["unknown", "malformed"])
    def test_unknown_cursor_is_refused(self, cursor):
        account = create_pf_account()

        status, response = RequestGenerator.GET_statement(account["account_key"], {"after": cursor})
        assert status == 422
        assert response["code"] == "QIT006001"

    @pytest.mark.parametrize(
        "query_params",
        [{"limit": "0"}, {"limit": "101"}, {"limit": "-1"}, {"limit": "abc"}, {"page": "2"}],
        ids=["zero", "above_max", "negative", "text", "unknown_param"],
    )
    def test_invalid_query_is_refused(self, query_params):
        account = create_pf_account()

        status, response = RequestGenerator.GET_statement(account["account_key"], query_params)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_accepts_the_max_limit(self):
        account = create_pf_account()
        receive_ted(account, 100)

        assert len(statement(account, limit=100)["movements"]) == 1

    def test_unknown_account(self):
        status, response = RequestGenerator.GET_statement(str(uuid4()))
        assert status == 404
        assert response["code"] == "QIT003001"


class TestStatementProvesTheBalance:
    def test_lines_chain_and_add_up_to_the_balance(self):
        company = create_pj_account()
        person = create_pf_account()
        receive_ted(company, 100000)
        receive_ted(person, 20000)
        for _ in range(22):
            pix(company, person["email"], 700)
        for _ in range(4):
            pix(person, company["email"], 1300)
        external_key = f"carlos.{uuid4()}@outrobanco.com.br"
        CentralBankMock.answer_pix(external_key, 200, CentralBankMock.confirmation())
        pix(company, external_key, 2000)
        pix(company, person["email"], 999999999)

        for account in (company, person):
            entries = list(reversed(all_entries(account)))
            balance = 0
            for entry in entries:
                signed_amount = entry["amount_cents"] if entry["direction"] == "CREDIT" else -entry["amount_cents"]
                balance += signed_amount
                assert entry["balance_after_cents"] == balance
            assert balance == balance_of(account)
