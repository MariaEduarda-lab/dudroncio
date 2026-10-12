from concurrent.futures import ThreadPoolExecutor

from tests.utils import PayloadGenerator, RequestGenerator


def assert_safe_response(response: dict) -> None:
    serialized = str(response).lower()
    for forbidden in ("password", "password_hash", "access_token", "'id'"):
        assert forbidden not in serialized


def test_pf_onboarding_creates_complete_active_account():
    payload = PayloadGenerator.create_pf_client_payload()
    status, response = RequestGenerator.POST_onboarding(payload)
    assert status == 201
    assert response["client"]["person_type"] == "PF"
    assert response["client"]["document_number"].startswith("***.***.***-")
    assert response["account"]["client_key"] == response["client"]["client_key"]
    assert response["account"]["status"] == "ACTIVE"
    assert response["account"]["balance_cents"] == 0
    assert_safe_response(response)


def test_pj_onboarding_masks_representative_and_is_safe():
    payload = PayloadGenerator.create_client_payload()
    status, response = RequestGenerator.POST_onboarding(payload)
    assert status == 201
    representative = response["client"]["legal_representatives"][0]
    assert representative["cpf"].startswith("***.***.***-")
    assert response["account"]["client_key"] == response["client"]["client_key"]
    assert_safe_response(response)


def test_onboarding_requires_internal_token_and_bearer_does_not_replace_it():
    payload = PayloadGenerator.create_pf_client_payload()
    status, response = RequestGenerator.POST_onboarding(payload, headers={"Authorization": "Bearer anything"})
    assert status == 403
    assert response["code"] == "QIT000002"


def test_concurrent_duplicate_onboarding_creates_at_most_one_complete_result():
    payload = PayloadGenerator.create_pf_client_payload()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: RequestGenerator.POST_onboarding(payload), range(2)))
    assert sorted(status for status, _ in results) == [201, 409]
    success = next(response for status, response in results if status == 201)
    status, account = RequestGenerator.GET_account(success["account"]["account_key"])
    assert status == 200
    assert account["client_key"] == success["client"]["client_key"]
