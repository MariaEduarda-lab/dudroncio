from datetime import date, datetime
from zoneinfo import ZoneInfo

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator


def only_alphanumeric(document_number: str) -> str:
    return "".join(character for character in document_number.upper() if character.isalnum())


def assert_does_not_expose(response: dict, document_number: str) -> None:
    assert document_number not in str(response)
    assert only_alphanumeric(document_number) not in str(response)


def birthdate_years_ago(years: int, days_later: int = 0) -> str:
    # Mesmo calendario do servidor: a maioridade conta no dia de Brasilia.
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    try:
        birthdate = today.replace(year=today.year - years)
    except ValueError:
        # 29/02 em ano que nao e bissexto
        birthdate = today.replace(year=today.year - years, day=28)
    return date.fromordinal(birthdate.toordinal() + days_later).isoformat()


class TestPjClient:
    def test_refuses_invalid_payload(self):
        status, response = RequestGenerator.POST_client({})
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_creates_and_gets_client_without_operational_status_or_sensitive_fields(self):
        payload = PayloadGenerator.create_client_payload()

        status, response = RequestGenerator.POST_client(payload)
        assert status == 201
        assert set(response) == {"client_key"}

        status, client = RequestGenerator.GET_client(response["client_key"])
        assert status == 200
        assert client["client_key"] == response["client_key"]
        assert client["person_type"] == "PJ"
        assert client["document_number"] == only_alphanumeric(payload["document_number"])
        assert client["legal_name"] == payload["legal_name"]
        assert client["trade_name"] == payload["trade_name"]
        assert client["primary_activity"] == payload["primary_activity"]
        assert client["cnpj_status"] == "ACTIVE"
        assert client["monthly_income_cents"] == payload["monthly_income_cents"]
        assert client["email"] == payload["email"]
        assert client["address"] == payload["address"]
        assert "status" not in client
        assert "id" not in client
        assert "password_hash" not in client
        assert "full_name" not in client
        assert "birthdate" not in client
        assert client["updated_at"] == client["created_at"]

        representative = client["legal_representatives"][0]
        assert representative["cpf"].startswith("***.***.***-")
        assert representative["cpf"].endswith(payload["legal_representative"]["cpf"][-2:])
        assert "password" not in representative
        assert "password_hash" not in representative
        assert "status" not in representative
        assert "id" not in representative
        assert representative["updated_at"] == representative["created_at"]

    def test_refuses_invalid_cnpj_without_exposing_it(self):
        payload = PayloadGenerator.create_client_payload(cnpj="11.111.111/1111-11")

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002002"
        assert_does_not_expose(response, payload["document_number"])

    def test_refuses_duplicated_cnpj_without_exposing_it(self):
        first = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        second = PayloadGenerator.create_client_payload(cnpj=only_alphanumeric(first["document_number"]))
        status, response = RequestGenerator.POST_client(second)
        assert status == 409
        assert response["code"] == "QIT002003"
        assert_does_not_expose(response, first["document_number"])

    def test_refuses_duplicated_representative_email(self):
        first = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        second = PayloadGenerator.create_client_payload(
            representative_email=first["legal_representative"]["email"]
        )
        status, response = RequestGenerator.POST_client(second)
        assert status == 409
        assert response["code"] == "QIT002004"

    def test_refuses_company_email_equal_to_its_own_representative_email(self):
        # CLI-06 literal: o e-mail nao se repete em lugar nenhum, nem
        # entre a empresa e o proprio representante.
        payload = PayloadGenerator.create_client_payload()
        payload["legal_representative"]["email"] = payload["email"]

        status, response = RequestGenerator.POST_client(payload)
        assert status == 409
        assert response["code"] == "QIT002004"

    def test_invalid_representative_does_not_leave_partial_client(self):
        payload = PayloadGenerator.create_client_payload()
        payload["legal_representative"]["cpf"] = "111.111.111-11"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002005"

        payload["legal_representative"]["cpf"] = RandomGenerator.generate_cpf()
        status, _ = RequestGenerator.POST_client(payload)
        assert status == 201

    def test_refuses_underage_representative(self):
        payload = PayloadGenerator.create_client_payload()
        payload["legal_representative"]["birthdate"] = birthdate_years_ago(18, days_later=1)

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002007"

    def test_client_not_found(self):
        status, response = RequestGenerator.GET_client("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT002001"

    def test_malformed_client_key_is_not_found(self):
        status, response = RequestGenerator.GET_client("nao-e-uma-chave")
        assert status == 404
        assert response["code"] == "QIT002001"

    def test_refuses_cnpj_status_sent_by_client(self):
        payload = PayloadGenerator.create_client_payload()
        payload["cnpj_status"] = "ACTIVE"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_cnpj_ineligible_in_registry(self):
        payload = PayloadGenerator.create_client_payload(cnpj="22.333.444/0001-81")

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002008"

    def test_refuses_company_without_representative(self):
        payload = PayloadGenerator.create_client_payload()
        del payload["legal_representative"]

        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_person_fields_in_company(self):
        for field, value in [("full_name", "Ana Souza"), ("birthdate", "1995-08-21"), ("password", "senha-forte-123")]:
            payload = PayloadGenerator.create_client_payload()
            payload[field] = value

            status, response = RequestGenerator.POST_client(payload)
            assert status == 400, field
            assert response["code"] == "QIT000001"

    def test_refuses_cpf_as_company_document(self):
        payload = PayloadGenerator.create_client_payload(cnpj=RandomGenerator.generate_cpf())

        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_old_fields(self):
        for field, value in [("client_type", "PJ"), ("segment", "PJ"), ("monthly_revenue_cents", 100)]:
            payload = PayloadGenerator.create_client_payload()
            payload[field] = value

            status, response = RequestGenerator.POST_client(payload)
            assert status == 400, field
            assert response["code"] == "QIT000001"

    def test_invalid_cpf_error_does_not_expose_cpf(self):
        payload = PayloadGenerator.create_client_payload()
        payload["legal_representative"]["cpf"] = "111.111.111-11"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert_does_not_expose(response, "111.111.111-11")

    def test_duplicated_cpf_error_does_not_expose_cpf(self):
        first = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        second = PayloadGenerator.create_client_payload()
        second["legal_representative"]["cpf"] = first["legal_representative"]["cpf"]
        status, response = RequestGenerator.POST_client(second)
        assert status == 409
        assert response["code"] == "QIT002006"
        assert_does_not_expose(response, first["legal_representative"]["cpf"])


class TestPfClient:
    def test_creates_and_gets_person(self):
        payload = PayloadGenerator.create_pf_client_payload()

        status, response = RequestGenerator.POST_client(payload)
        assert status == 201
        assert set(response) == {"client_key"}

        status, client = RequestGenerator.GET_client(response["client_key"])
        assert status == 200
        assert set(client) == {
            "client_key",
            "person_type",
            "document_number",
            "full_name",
            "birthdate",
            "monthly_income_cents",
            "email",
            "phone_number",
            "address",
            "created_at",
            "updated_at",
        }
        assert client["client_key"] == response["client_key"]
        assert client["person_type"] == "PF"
        assert client["document_number"] == f"***.***.***-{payload['document_number'][-2:]}"
        assert client["full_name"] == payload["full_name"]
        assert client["birthdate"] == payload["birthdate"]
        assert client["monthly_income_cents"] == payload["monthly_income_cents"]
        assert client["email"] == payload["email"]
        assert client["phone_number"] == payload["phone_number"]
        assert client["address"] == payload["address"]
        assert client["updated_at"] == client["created_at"]

    def test_person_opens_account(self):
        status, response = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload())
        assert status == 201

        status, account = RequestGenerator.POST_account(response["client_key"])
        assert status == 201

        status, account = RequestGenerator.GET_account(account["account_key"])
        assert status == 200
        assert account["client_key"] == response["client_key"]

    def test_accepts_cpf_without_mask(self):
        payload = PayloadGenerator.create_pf_client_payload(cpf=only_alphanumeric(RandomGenerator.generate_cpf()))

        status, _ = RequestGenerator.POST_client(payload)
        assert status == 201

    def test_refuses_invalid_cpf_without_exposing_it(self):
        payload = PayloadGenerator.create_pf_client_payload(cpf="123.456.789-00")

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002009"
        assert_does_not_expose(response, payload["document_number"])

    def test_refuses_cpf_with_all_equal_digits(self):
        payload = PayloadGenerator.create_pf_client_payload(cpf="11111111111")

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002009"

    def test_refuses_duplicated_cpf_with_or_without_mask(self):
        first = PayloadGenerator.create_pf_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        for cpf in [first["document_number"], only_alphanumeric(first["document_number"])]:
            status, response = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(cpf=cpf))
            assert status == 409
            assert response["code"] == "QIT002010"
            assert_does_not_expose(response, first["document_number"])

    def test_refuses_underage_person(self):
        payload = PayloadGenerator.create_pf_client_payload()
        payload["birthdate"] = birthdate_years_ago(18, days_later=1)

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002011"

    def test_accepts_person_turning_eighteen_today(self):
        payload = PayloadGenerator.create_pf_client_payload()
        payload["birthdate"] = birthdate_years_ago(18)

        status, _ = RequestGenerator.POST_client(payload)
        assert status == 201

    def test_refuses_impossible_birthdate(self):
        payload = PayloadGenerator.create_pf_client_payload()
        payload["birthdate"] = "1990-02-30"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 422
        assert response["code"] == "QIT002011"

    def test_refuses_email_already_used_by_a_person(self):
        first = PayloadGenerator.create_pf_client_payload()
        status, _ = RequestGenerator.POST_client(first)
        assert status == 201

        attempts = [
            PayloadGenerator.create_pf_client_payload(email=first["email"]),
            PayloadGenerator.create_client_payload(email=first["email"]),
            PayloadGenerator.create_client_payload(representative_email=first["email"]),
        ]
        for attempt in attempts:
            status, response = RequestGenerator.POST_client(attempt)
            assert status == 409
            assert response["code"] == "QIT002004"

    def test_refuses_person_email_already_used_by_company_or_representative(self):
        company = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(company)
        assert status == 201

        for email in [company["email"], company["legal_representative"]["email"]]:
            status, response = RequestGenerator.POST_client(PayloadGenerator.create_pf_client_payload(email=email))
            assert status == 409
            assert response["code"] == "QIT002004"

    def test_person_cpf_can_be_a_company_representative(self):
        # Decisao de 04/10: o titular PF pode representar uma PJ.
        person = PayloadGenerator.create_pf_client_payload()
        status, _ = RequestGenerator.POST_client(person)
        assert status == 201

        company = PayloadGenerator.create_client_payload()
        company["legal_representative"]["cpf"] = person["document_number"]
        status, _ = RequestGenerator.POST_client(company)
        assert status == 201

    def test_representative_cpf_can_register_as_person(self):
        company = PayloadGenerator.create_client_payload()
        status, _ = RequestGenerator.POST_client(company)
        assert status == 201

        person = PayloadGenerator.create_pf_client_payload(cpf=company["legal_representative"]["cpf"])
        status, _ = RequestGenerator.POST_client(person)
        assert status == 201

    def test_refuses_company_fields_in_person(self):
        company_fields = [
            ("legal_name", "Empresa Ltda"),
            ("trade_name", "Empresa"),
            ("primary_activity", "Comercio"),
            ("cnpj_status", "ACTIVE"),
            ("legal_representative", PayloadGenerator.create_client_payload()["legal_representative"]),
        ]
        for field, value in company_fields:
            payload = PayloadGenerator.create_pf_client_payload()
            payload[field] = value

            status, response = RequestGenerator.POST_client(payload)
            assert status == 400, field
            assert response["code"] == "QIT000001"

    def test_refuses_missing_person_field(self):
        for field in ["full_name", "birthdate", "password", "monthly_income_cents"]:
            payload = PayloadGenerator.create_pf_client_payload()
            del payload[field]

            status, response = RequestGenerator.POST_client(payload)
            assert status == 400, field
            assert response["code"] == "QIT000001"

    def test_refuses_cnpj_as_person_document(self):
        payload = PayloadGenerator.create_pf_client_payload(cpf=RandomGenerator.generate_cnpj())

        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_unknown_person_types(self):
        for person_type in ["BANCO", "MEI", "pf", None]:
            payload = PayloadGenerator.create_pf_client_payload()
            payload["person_type"] = person_type

            status, response = RequestGenerator.POST_client(payload)
            assert status == 400, person_type
            assert response["code"] == "QIT000001"

    def test_refuses_short_password(self):
        payload = PayloadGenerator.create_pf_client_payload()
        payload["password"] = "curta"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_bad_request_does_not_echo_document_or_password(self):
        payload = PayloadGenerator.create_pf_client_payload()
        payload["password"] = "senha-secreta-do-teste"
        payload["legal_name"] = "Empresa Ltda"

        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert response["code"] == "QIT000001"
        assert "legal_name" in response["description"]
        assert payload["password"] not in str(response)
        assert_does_not_expose(response, payload["document_number"])

        payload = PayloadGenerator.create_pf_client_payload(cpf="529.982.247")
        status, response = RequestGenerator.POST_client(payload)
        assert status == 400
        assert "document_number" in response["description"]
        assert "529.982.247" not in str(response)
