import pytest

from utils.account_number import account_check_digit, generate_account_number


@pytest.mark.parametrize(
    "account_number, expected_digit",
    [
        ("12345678", "9"),
        # Conta de receita do banco (repo-docs/banco/dados-iniciais.md): 00000001-9.
        ("00000001", "9"),
        # Resto 1 daria 10: o digito vira 0.
        ("00000006", "0"),
        # Resto 0 daria 11: o digito vira 0.
        ("00000000", "0"),
    ],
)
def test_check_digit_uses_modulo_11(account_number, expected_digit):
    assert account_check_digit(account_number) == expected_digit


def test_generated_number_has_eight_digits():
    for _ in range(100):
        account_number = generate_account_number()
        assert len(account_number) == 8
        assert account_number.isdigit()


def test_generated_numbers_are_not_repeated_in_sequence():
    numbers = {generate_account_number() for _ in range(100)}
    assert len(numbers) > 90
