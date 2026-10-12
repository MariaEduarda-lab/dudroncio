from tests.utils import PayloadGenerator, RequestGenerator


INJECTION = "x@example.test' OR '1'='1' --"


def test_external_inputs_never_become_sql_commands():
    payload = PayloadGenerator.create_pf_client_payload()
    status, onboarding = RequestGenerator.POST_onboarding(payload)
    assert status == 201
    account_key = onboarding["account"]["account_key"]

    status, _ = RequestGenerator.POST_auth_token(INJECTION, "irrelevant")
    assert status == 400

    status, _ = RequestGenerator.GET_account(INJECTION)
    assert status == 404

    status, _ = RequestGenerator.POST_transaction(
        account_key,
        PayloadGenerator.create_pix_send_payload(payload["email"], 1),
        INJECTION,
    )
    assert status == 400

    status, _ = RequestGenerator.POST_transaction(
        account_key,
        PayloadGenerator.create_pix_send_payload(INJECTION, 1),
        "injection-pix-key",
    )
    assert status == 422

    status, _ = RequestGenerator.GET_statement(account_key, {"after": INJECTION})
    assert status == 422

    status, account = RequestGenerator.GET_account(account_key)
    assert status == 200
    assert account["balance_cents"] == 0
    status, statement = RequestGenerator.GET_statement(account_key)
    assert status == 200
    assert statement["movements"] == []
