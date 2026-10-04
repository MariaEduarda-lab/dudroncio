import random
import string


class RandomGenerator:
    @staticmethod
    def generate_cpf():
        cpf = [random.randrange(10) for _ in range(9)]
        for _ in range(2):
            value = sum([(len(cpf) + 1 - i) * v for i, v in enumerate(cpf)]) % 11
            cpf.append(11 - value if value > 1 else 0)
        cpf_number = "".join(str(x) for x in cpf)
        cpf_number = f"{cpf_number[0:3]}.{cpf_number[3:6]}.{cpf_number[6:9]}-{cpf_number[9:11]}"
        return cpf_number

    @staticmethod
    def generate_cnpj():
        cnpj = [random.randrange(10) for _ in range(8)] + [0, 0, 0, 1]

        for _ in range(2):
            value = sum(v * (i % 8 + 2) for i, v in enumerate(reversed(cnpj)))
            digit = 11 - value % 11
            cnpj.append(digit if digit < 10 else 0)

        cnpj_number = "".join(str(x) for x in cnpj)

        cnpj_number = (
            f"{cnpj_number[0:2]}.{cnpj_number[2:5]}.{cnpj_number[5:8]}/{cnpj_number[8:12]}-{cnpj_number[12:14]}"
        )

        return cnpj_number

    @staticmethod
    def generate_alphanumeric_cnpj():
        """CNPJ alfanumerico valido, sem mascara: letras valem o codigo ASCII menos 48."""
        base = [random.choice(string.digits + string.ascii_uppercase) for _ in range(8)] + list("0001")
        if not any(character.isalpha() for character in base):
            return RandomGenerator.generate_alphanumeric_cnpj()

        values = [ord(character) - 48 for character in base]
        for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
            remainder = sum(value * weight for value, weight in zip(values, weights)) % 11
            values.append(0 if remainder < 2 else 11 - remainder)
        return "".join(base) + "".join(str(digit) for digit in values[12:])
