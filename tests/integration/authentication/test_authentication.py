import pytest

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.requisition import ClientRequisition


PASSWORD = "senha-forte-123"


def onboard_and_login(payload: dict, login_email: str) -> tuple[dict, str]:
    status, onboarding = RequestGenerator.POST_onboarding(payload)
    assert status == 201
    status, authentication = RequestGenerator.POST_auth_token(login_email, PASSWORD)
    assert status == 200
    assert authentication["token_type"] == "Bearer"
    assert authentication["expires_in"] > 0
    return onboarding, authentication["access_token"]


def test_pf_and_pj_representative_can_login():
    pf = PayloadGenerator.create_pf_client_payload()
    _, pf_token = onboard_and_login(pf, pf["email"].upper())
    assert pf_token
    pj = PayloadGenerator.create_client_payload()
    _, pj_token = onboard_and_login(pj, pj["legal_representative"]["email"])
    assert pj_token


def test_company_email_wrong_password_and_unknown_identity_are_indistinguishable():
    pj = PayloadGenerator.create_client_payload()
    RequestGenerator.POST_onboarding(pj)
    attempts = [
        (pj["email"], PASSWORD),
        (pj["legal_representative"]["email"], "wrong-password"),
        ("unknown@example.com", "wrong-password"),
    ]
    responses = [RequestGenerator.POST_auth_token(email, password) for email, password in attempts]
    assert [status for status, _ in responses] == [401, 401, 401]
    assert responses[0][1] == responses[1][1] == responses[2][1]


@pytest.mark.parametrize("token", [None, "invalid", "a.b"])
def test_authenticated_routes_reject_missing_or_invalid_token(token):
    status, response = RequestGenerator.GET_authenticated_statement(token)
    assert status == 401
    assert response["code"] == "QIT007001"


def test_internal_token_does_not_open_customer_route_and_bearer_does_not_open_legacy_route():
    status, response = RequestGenerator.GET_authenticated_statement(
        None, extra_headers={"INTERNAL-TOKEN": "default_token"}
    )
    assert status == 401
    status, response = RequestGenerator.POST_onboarding(
        PayloadGenerator.create_pf_client_payload(), headers={"Authorization": "Bearer invalid"}
    )
    assert status == 403


def test_valid_identity_without_account_gets_generic_not_found():
    payload = PayloadGenerator.create_pf_client_payload()
    status, _ = RequestGenerator.POST_client(payload)
    assert status == 201
    status, authentication = RequestGenerator.POST_auth_token(payload["email"], PASSWORD)
    assert status == 200
    status, response = RequestGenerator.GET_authenticated_statement(authentication["access_token"])
    assert status == 404
    assert response["code"] == "QIT007002"


def test_adulterated_real_token_is_rejected():
    payload = PayloadGenerator.create_pf_client_payload()
    _, token = onboard_and_login(payload, payload["email"])
    status, response = RequestGenerator.GET_authenticated_statement(token + "x")
    assert status == 401
    assert response["code"] == "QIT007001"


def test_account_key_in_alternate_path_does_not_become_customer_authorization():
    payload = PayloadGenerator.create_pf_client_payload()
    onboarding, token = onboard_and_login(payload, payload["email"])
    response = ClientRequisition.send(
        "POST",
        f"/transactions/{onboarding['account']['account_key']}",
        payload={"type": "PIX", "amount_cents": 1, "pix_key": payload["email"]},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "alternate-path"},
    )
    assert response.response_status in (403, 404)
