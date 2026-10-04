from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator


# Cadastros simultâneos com o mesmo e-mail ou documento: só o banco de
# dados consegue garantir que um deles vence (CLI-02, CLI-06). Uma checagem
# "SELECT antes do INSERT" deixa os dois passarem, ou estoura em 500.

PARALLEL_REQUESTS = 12


def post_all_at_once(payloads: list[dict]) -> list[tuple[int, dict]]:
    barrier = Barrier(len(payloads))

    def post(payload):
        barrier.wait()
        return RequestGenerator.POST_client(payload)

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        return list(executor.map(post, payloads))


def assert_only_one_wins(results: list[tuple[int, dict]], conflict_code: str):
    statuses = Counter(status for status, _ in results)
    assert statuses[201] == 1, results
    assert statuses[409] == len(results) - 1, results
    for status, response in results:
        if status == 409:
            assert response["code"] == conflict_code


def unique_email(prefix: str) -> str:
    return f"{prefix}.{uuid4()}@exemplo.com.br"


class TestSimultaneousRegistrations:
    @pytest.mark.parametrize("round_number", range(3))
    def test_same_email_as_pf_company_and_representative(self, round_number):
        email = unique_email("disputado")
        payloads = []
        for index in range(PARALLEL_REQUESTS):
            kind = index % 3
            if kind == 0:
                payloads.append(PayloadGenerator.create_pf_client_payload(email=email))
            elif kind == 1:
                payloads.append(PayloadGenerator.create_client_payload(email=email))
            else:
                payloads.append(PayloadGenerator.create_client_payload(representative_email=email))

        assert_only_one_wins(post_all_at_once(payloads), "QIT002004")

    def test_same_email_in_different_case(self):
        email = unique_email("caixa")
        payloads = [
            PayloadGenerator.create_pf_client_payload(email=email.upper() if index % 2 else email)
            for index in range(PARALLEL_REQUESTS)
        ]

        assert_only_one_wins(post_all_at_once(payloads), "QIT002004")

    def test_same_pf_cpf_with_and_without_mask(self):
        cpf = RandomGenerator.generate_cpf()
        digits = "".join(character for character in cpf if character.isdigit())
        payloads = [
            PayloadGenerator.create_pf_client_payload(cpf=cpf if index % 2 else digits)
            for index in range(PARALLEL_REQUESTS)
        ]

        assert_only_one_wins(post_all_at_once(payloads), "QIT002010")

    def test_same_cnpj(self):
        cnpj = RandomGenerator.generate_cnpj()
        payloads = [PayloadGenerator.create_client_payload(cnpj=cnpj) for _ in range(PARALLEL_REQUESTS)]

        assert_only_one_wins(post_all_at_once(payloads), "QIT002003")

    def test_same_representative_cpf_in_different_companies(self):
        cpf = RandomGenerator.generate_cpf()
        payloads = []
        for _ in range(PARALLEL_REQUESTS):
            payload = PayloadGenerator.create_client_payload()
            payload["legal_representative"]["cpf"] = cpf
            payloads.append(payload)

        assert_only_one_wins(post_all_at_once(payloads), "QIT002006")
