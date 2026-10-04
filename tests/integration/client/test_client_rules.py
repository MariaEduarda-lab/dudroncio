from uuid import uuid4

import pytest

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator, INTERNAL_TOKEN
from tests.utils.requisition import ClientRequisition


# Regras do 01-cliente.md que o test_client_flow.py não cobre: CNPJ
# alfanumérico (CLI-03), documento guardado sem máscara e em maiúsculas
# (CLI-04), e-mail sem diferença de maiúsculas (CLI-06) e cadastro que não
# muda nem some (CLI-07, CLI-08, CLI-09).


def alphanumeric_cnpj() -> str:
    return RandomGenerator.generate_alphanumeric_cnpj()


def masked(cnpj: str) -> str:
    return f"{cnpj[0:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"


def unique_email(prefix: str) -> str:
    return f"{prefix}.{uuid4()}@exemplo.com.br"


def send(method: str, endpoint: str, payload: dict = None):
    response = ClientRequisition.send(method, endpoint, payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})
    return response.response_status, response.response_json


class TestAlphanumericCnpj:
    def test_creates_pj_with_alphanumeric_cnpj(self):
        cnpj = alphanumeric_cnpj()
        status, response = RequestGenerator.POST_client(PayloadGenerator.create_client_payload(cnpj=masked(cnpj)))
        assert status == 201, response

        status, client = RequestGenerator.GET_client(response["client_key"])
        assert status == 200
        assert client["document_number"] == cnpj

    def test_lowercase_cnpj_is_stored_in_uppercase(self):
        cnpj = alphanumeric_cnpj()
        status, response = RequestGenerator.POST_client(
            PayloadGenerator.create_client_payload(cnpj=masked(cnpj).lower())
        )
        assert status == 201, response

        status, client = RequestGenerator.GET_client(response["client_key"])
        assert client["document_number"] == cnpj

    def test_same_cnpj_with_other_case_and_mask_is_duplicated(self):
        cnpj = alphanumeric_cnpj()
        status, _ = RequestGenerator.POST_client(PayloadGenerator.create_client_payload(cnpj=masked(cnpj).lower()))
        assert status == 201

        status, response = RequestGenerator.POST_client(PayloadGenerator.create_client_payload(cnpj=cnpj))
        assert status == 409
        assert response["code"] == "QIT002003"

    def test_refuses_alphanumeric_cnpj_with_wrong_check_digits(self):
        cnpj = alphanumeric_cnpj()
        wrong_digit = str((int(cnpj[13]) + 1) % 10)
        status, response = RequestGenerator.POST_client(
            PayloadGenerator.create_client_payload(cnpj=cnpj[:13] + wrong_digit)
        )
        assert status == 422
        assert response["code"] == "QIT002002"

    def test_refuses_letters_in_cnpj_check_digits(self):
        cnpj = alphanumeric_cnpj()
        status, response = RequestGenerator.POST_client(PayloadGenerator.create_client_payload(cnpj=cnpj[:12] + "AB"))
        assert status in (400, 422)
        assert response["code"] in ("QIT000001", "QIT002002")


class TestEmailIgnoresCase:
    def test_email_is_stored_in_lowercase(self):
        email = unique_email("Ana.Souza").upper()
        status, response = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(email=email))
        assert status == 201, response

        status, client = RequestGenerator.GET_client(response["client_key"])
        assert client["email"] == email.lower()

    def test_same_email_in_other_case_is_duplicated_between_pf(self):
        email = unique_email("ana")
        status, _ = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(email=email))
        assert status == 201

        status, response = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(email=email.upper()))
        assert status == 409
        assert response["code"] == "QIT002004"

    def test_representative_email_in_other_case_is_duplicated_with_pf_email(self):
        email = unique_email("pedro")
        status, _ = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(email=email))
        assert status == 201

        status, response = RequestGenerator.POST_client(
            PayloadGenerator.create_client_payload(representative_email=email.upper())
        )
        assert status == 409
        assert response["code"] == "QIT002004"

    def test_pf_email_in_other_case_is_duplicated_with_company_email(self):
        email = unique_email("financeiro")
        status, _ = RequestGenerator.POST_client(PayloadGenerator.create_client_payload(email=email.upper()))
        assert status == 201

        status, response = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(email=email))
        assert status == 409
        assert response["code"] == "QIT002004"


class TestClientNeverChangesNorDisappears:
    @pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
    def test_there_is_no_route_to_change_or_delete_a_client(self, method):
        payload = PayloadGenerator.create_pf_client_payload()
        status, response = RequestGenerator.POST_client(payload)
        assert status == 201
        client_key = response["client_key"]
        status, before = RequestGenerator.GET_client(client_key)

        body = None if method == "DELETE" else {"email": unique_email("nova"), "document_number": "52998224725"}
        status, _ = send(method, f"/clients/{client_key}", body)
        assert status == 405

        status, after = RequestGenerator.GET_client(client_key)
        assert status == 200
        assert after == before
