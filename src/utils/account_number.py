import secrets

ACCOUNT_NUMBER_LENGTH = 8


def generate_account_number() -> str:
    """Sorteia os 8 digitos da conta.

    Usa `secrets`, e nao `random`: numero de conta sequencial ou
    previsivel facilita adivinhar contas de outros clientes.
    """
    return "".join(str(secrets.randbelow(10)) for _ in range(ACCOUNT_NUMBER_LENGTH))


def account_check_digit(account_number: str) -> str:
    """Digito verificador pelo modulo 11.

    Pesos de 2 a 9 da direita para a esquerda; o digito e 11 menos o
    resto da soma por 11. Quando a conta da 10 ou 11, o digito vira 0.
    """
    total = 0
    for digit, weight in zip(reversed(account_number), range(2, 10)):
        total = total + int(digit) * weight

    digit = 11 - total % 11
    if digit >= 10:
        return "0"
    return str(digit)
