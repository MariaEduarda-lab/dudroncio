from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from tests.utils import CentralBankMock, PayloadGenerator, RequestGenerator


# Checkpoint do 07-escopo.md: o saldo continua certo quando os pedidos
# chegam ao mesmo tempo. Nenhum saldo negativo, nenhum erro 500, nenhuma
# vaga gratis usada duas vezes e nenhum centavo criado ou perdido.

PIX_FEE = 99


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


def fund(account: dict, amount_cents: int) -> None:
    status, _ = RequestGenerator.POST_webhook_central_bank_ted(
        PayloadGenerator.create_incoming_ted_payload(account, amount_cents=amount_cents)
    )
    assert status == 201


def balance_of(account: dict) -> int:
    status, current = RequestGenerator.GET_account(account["account_key"])
    assert status == 200
    return current["balance_cents"]


def pix(sender: dict, pix_key: str, amount_cents: int):
    return RequestGenerator.POST_transaction(
        sender["account_key"], PayloadGenerator.create_pix_send_payload(pix_key, amount_cents), str(uuid4())
    )


def in_parallel(calls: list) -> list:
    with ThreadPoolExecutor(max_workers=len(calls)) as executor:
        return list(executor.map(lambda call: call(), calls))


class TestConcurrentTransfers:
    def test_crossed_transfers_never_lose_money_nor_fail(self):
        first = create_pf_account()
        second = create_pf_account()
        fund(first, 100000)
        fund(second, 100000)

        calls = [lambda: pix(first, second["email"], 1000) for _ in range(10)]
        calls += [lambda: pix(second, first["email"], 1000) for _ in range(10)]
        results = in_parallel(calls)

        assert [status for status, _ in results] == [201] * 20
        assert balance_of(first) == 100000
        assert balance_of(second) == 100000

    def test_crossed_transfers_with_little_balance_never_go_negative(self):
        first = create_pf_account()
        second = create_pf_account()
        fund(first, 3000)
        fund(second, 3000)

        calls = [lambda: pix(first, second["email"], 1000) for _ in range(10)]
        calls += [lambda: pix(second, first["email"], 1000) for _ in range(10)]
        results = in_parallel(calls)

        statuses = [status for status, _ in results]
        assert set(statuses) <= {201, 422}
        assert balance_of(first) >= 0
        assert balance_of(second) >= 0
        assert balance_of(first) + balance_of(second) == 6000

    def test_two_sends_that_do_not_fit_together_only_one_happens(self):
        sender = create_pf_account()
        recipient = create_pf_account()
        fund(sender, 10000)

        results = in_parallel([lambda: pix(sender, recipient["email"], 8000) for _ in range(2)])

        assert sorted(status for status, _ in results) == [201, 422]
        assert balance_of(sender) == 2000
        assert balance_of(recipient) == 8000

    def test_many_sends_spend_exactly_what_the_balance_allows(self):
        sender = create_pf_account()
        recipient = create_pf_account()
        fund(sender, 1000)

        results = in_parallel([lambda: pix(sender, recipient["email"], 300) for _ in range(10)])

        assert sorted(status for status, _ in results) == [201] * 3 + [422] * 7
        assert balance_of(sender) == 100
        assert balance_of(recipient) == 900


class TestConcurrentQuota:
    def test_two_sends_at_the_quota_limit_are_never_both_free(self):
        sender = create_pj_account()
        recipient = create_pf_account()
        fund(sender, 100000)
        for _ in range(19):
            assert pix(sender, recipient["email"], 100)[0] == 201

        results = in_parallel([lambda: pix(sender, recipient["email"], 100) for _ in range(2)])

        assert [status for status, _ in results] == [201, 201]
        assert sorted(transaction["fee_cents"] for _, transaction in results) == [0, PIX_FEE]
        assert balance_of(sender) == 100000 - 21 * 100 - PIX_FEE

    def test_many_sends_around_the_quota_limit_use_each_free_slot_once(self):
        sender = create_pj_account()
        recipient = create_pf_account()
        fund(sender, 100000)
        for _ in range(18):
            assert pix(sender, recipient["email"], 100)[0] == 201

        results = in_parallel([lambda: pix(sender, recipient["email"], 100) for _ in range(5)])

        assert sorted(transaction["fee_cents"] for _, transaction in results) == [0, 0, PIX_FEE, PIX_FEE, PIX_FEE]
        assert balance_of(sender) == 100000 - 23 * 100 - 3 * PIX_FEE


class TestConcurrentExternalSends:
    def test_parallel_external_sends_only_reach_the_central_bank_while_there_is_balance(self):
        sender = create_pf_account()
        fund(sender, 2500)
        pix_key = f"carlos.{uuid4()}@outrobanco.com.br"
        CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation())

        results = in_parallel([lambda: pix(sender, pix_key, 1000) for _ in range(3)])

        assert sorted(status for status, _ in results) == [201, 201, 422]
        assert balance_of(sender) == 500
        assert CentralBankMock.pix_calls(pix_key) == 2


class TestConservation:
    def test_balances_equal_received_minus_sent_out_minus_fees(self):
        company = create_pj_account()
        person = create_pf_account()
        other_person = create_pf_account()
        received = 0
        for account, amount in [(company, 100000), (person, 50000)]:
            fund(account, amount)
            received += amount
        status, _ = RequestGenerator.POST_webhook_central_bank_pix(
            PayloadGenerator.create_incoming_pix_payload(other_person["email"], amount_cents=7000)
        )
        assert status == 201
        received += 7000

        external_key = f"carlos.{uuid4()}@outrobanco.com.br"
        CentralBankMock.answer_pix(external_key, 200, CentralBankMock.confirmation())
        refused_key = f"recusado.{uuid4()}@outrobanco.com.br"
        CentralBankMock.answer_pix(refused_key, 422)

        calls = [lambda: pix(company, person["email"], 500) for _ in range(12)]
        calls += [lambda: pix(company, other_person["email"], 700) for _ in range(12)]
        calls += [lambda: pix(person, company["email"], 300) for _ in range(5)]
        calls += [lambda: pix(other_person, person["email"], 2000) for _ in range(5)]
        calls += [lambda: pix(person, external_key, 1500) for _ in range(3)]
        calls += [lambda: pix(company, external_key, 2500) for _ in range(2)]
        calls += [lambda: pix(company, refused_key, 1000) for _ in range(2)]
        results = in_parallel(calls)

        assert all(status in (201, 422) for status, _ in results)
        done = [transaction for status, transaction in results if status == 201]
        sent_out = sum(t["amount_cents"] for t in done if t["recipient"]["bank_code"] != "999")
        fees = sum(t["fee_cents"] for t in done)
        assert fees > 0
        balances = sum(balance_of(account) for account in (company, person, other_person))
        assert balances == received - sent_out - fees
