from tests.integration.authentication.test_authentication import onboard_and_login
from tests.utils import PayloadGenerator, RequestGenerator


def test_authenticated_statement_is_scoped_and_paginated():
    first_payload = PayloadGenerator.create_pf_client_payload()
    first, first_token = onboard_and_login(first_payload, first_payload["email"])
    second_payload = PayloadGenerator.create_pf_client_payload()
    second, second_token = onboard_and_login(second_payload, second_payload["email"])
    for amount in (100, 200):
        status, _ = RequestGenerator.POST_webhook_central_bank_ted(
            PayloadGenerator.create_incoming_ted_payload(first["account"], amount_cents=amount)
        )
        assert status == 201
    status, empty = RequestGenerator.GET_authenticated_statement(second_token)
    assert status == 200
    assert empty == {"movements": [], "next_cursor": None}
    status, page = RequestGenerator.GET_authenticated_statement(first_token, {"limit": 1})
    assert status == 200
    assert len(page["movements"]) == 1
    assert page["next_cursor"] is not None
    status, response = RequestGenerator.GET_authenticated_statement(second_token, {"after": page["next_cursor"]})
    assert status == 422
    assert response["code"] == "QIT006001"


def test_statement_rejects_account_selection_inputs():
    payload = PayloadGenerator.create_pf_client_payload()
    onboarding, token = onboard_and_login(payload, payload["email"])
    account_key = onboarding["account"]["account_key"]
    status, response = RequestGenerator.GET_authenticated_statement(token, {"account_key": account_key})
    assert status == 400
    status, response = RequestGenerator.GET_authenticated_statement(token, extra_headers={"account-key": account_key})
    assert status == 400
