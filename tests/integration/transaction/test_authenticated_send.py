from uuid import uuid4

from tests.integration.authentication.test_authentication import onboard_and_login
from tests.utils import CentralBankMock, PayloadGenerator, RequestGenerator


def fund(account: dict, amount_cents: int = 50000):
    status, _ = RequestGenerator.POST_webhook_central_bank_ted(
        PayloadGenerator.create_incoming_ted_payload(account, amount_cents=amount_cents)
    )
    assert status == 201


def test_authenticated_pix_uses_token_account_and_is_idempotent():
    sender_payload = PayloadGenerator.create_pf_client_payload()
    sender, token = onboard_and_login(sender_payload, sender_payload["email"])
    recipient_payload = PayloadGenerator.create_pf_client_payload()
    recipient, _ = onboard_and_login(recipient_payload, recipient_payload["email"])
    fund(sender["account"])
    payload = PayloadGenerator.create_pix_send_payload(recipient_payload["email"], 1000)
    key = str(uuid4())
    first_status, first = RequestGenerator.POST_authenticated_transaction(token, payload, key)
    second_status, second = RequestGenerator.POST_authenticated_transaction(token, payload, key)
    assert first_status == 201
    assert second_status == 200
    assert first == second
    assert first["account_key"] == sender["account"]["account_key"]
    assert first["recipient"]["account_number"] == (
        f"{recipient['account']['account_number']}-{recipient['account']['check_digit']}"
    )


def test_authenticated_ted_and_account_key_injection_are_handled_safely():
    sender_payload = PayloadGenerator.create_pf_client_payload()
    sender, token = onboard_and_login(sender_payload, sender_payload["email"])
    recipient_payload = PayloadGenerator.create_pf_client_payload()
    recipient, _ = onboard_and_login(recipient_payload, recipient_payload["email"])
    fund(sender["account"])
    ted = PayloadGenerator.create_ted_send_payload(recipient["account"], 1000)
    status, _ = RequestGenerator.POST_authenticated_transaction(token, ted, str(uuid4()))
    assert status == 201
    for payload, query, headers in (
        ({**ted, "account_key": recipient["account"]["account_key"]}, None, None),
        (ted, {"account_key": recipient["account"]["account_key"]}, None),
        (ted, None, {"account-key": recipient["account"]["account_key"]}),
    ):
        status, response = RequestGenerator.POST_authenticated_transaction(
            token, payload, str(uuid4()), query_params=query, extra_headers=headers
        )
        assert status == 400
        assert response["code"] == "QIT000001"


def test_authenticated_pix_and_ted_to_other_bank_reuse_external_flow():
    sender_payload = PayloadGenerator.create_pf_client_payload()
    sender, token = onboard_and_login(sender_payload, sender_payload["email"])
    fund(sender["account"], 100000)

    pix_key = f"external.{uuid4()}@otherbank.example"
    CentralBankMock.answer_pix(pix_key, 200, CentralBankMock.confirmation())
    status, pix = RequestGenerator.POST_authenticated_transaction(
        token, PayloadGenerator.create_pix_send_payload(pix_key, 1000), str(uuid4())
    )
    assert status == 201
    assert pix["recipient"]["bank_code"] == "237"

    external_account = {"branch": "4321", "account_number": "87654321", "check_digit": "0"}
    CentralBankMock.answer_ted(external_account["account_number"], 200, CentralBankMock.confirmation())
    status, ted = RequestGenerator.POST_authenticated_transaction(
        token,
        PayloadGenerator.create_ted_send_payload(external_account, 1000, bank_code="237"),
        str(uuid4()),
    )
    assert status == 201
    assert ted["recipient"]["bank_code"] == "237"


def test_authenticated_company_reuses_tariff_quota_rules():
    company_payload = PayloadGenerator.create_client_payload()
    company, token = onboard_and_login(
        company_payload, company_payload["legal_representative"]["email"]
    )
    recipient_payload = PayloadGenerator.create_pf_client_payload()
    onboard_and_login(recipient_payload, recipient_payload["email"])
    fund(company["account"], 100000)
    payload = PayloadGenerator.create_pix_send_payload(recipient_payload["email"], 100)

    transactions = []
    for _ in range(21):
        status, transaction = RequestGenerator.POST_authenticated_transaction(token, payload, str(uuid4()))
        assert status == 201
        transactions.append(transaction)

    assert all(transaction["fee_cents"] == 0 for transaction in transactions[:20])
    assert transactions[20]["fee_cents"] == 99
