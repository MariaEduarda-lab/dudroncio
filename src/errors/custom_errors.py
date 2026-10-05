from errors import QIException


class NotFoundClient(QIException):
    code = "QIT002001"

    def __init__(self, client_key) -> None:
        super().__init__(
            "Client not found",
            self.code,
            404,
            f"Client with key {client_key} was not found.",
            "O cliente informado não foi encontrado.",
        )


class InvalidCnpj(QIException):
    code = "QIT002002"

    def __init__(self) -> None:
        super().__init__(
            "Invalid CNPJ",
            self.code,
            422,
            "The CNPJ is invalid.",
            "O CNPJ informado não é válido.",
        )


class DuplicatedCnpj(QIException):
    code = "QIT002003"

    def __init__(self) -> None:
        super().__init__(
            "CNPJ already registered",
            self.code,
            409,
            "There is already a client with this CNPJ.",
            "Já existe um cliente cadastrado com este CNPJ.",
        )


class DuplicatedClientEmail(QIException):
    code = "QIT002004"

    def __init__(self) -> None:
        super().__init__(
            "Email already registered",
            self.code,
            409,
            "There is already a client or representative with this email.",
            "Já existe um cadastro com este e-mail.",
        )


class InvalidRepresentativeCpf(QIException):
    code = "QIT002005"

    def __init__(self) -> None:
        super().__init__(
            "Invalid representative CPF",
            self.code,
            422,
            "The legal representative CPF is invalid.",
            "O CPF do representante legal não é válido.",
        )


class DuplicatedRepresentativeCpf(QIException):
    code = "QIT002006"

    def __init__(self) -> None:
        super().__init__(
            "Representative CPF already registered",
            self.code,
            409,
            "There is already a legal representative with this CPF.",
            "Já existe um representante legal cadastrado com este CPF.",
        )


class InvalidRepresentativeBirthdate(QIException):
    code = "QIT002007"

    def __init__(self, birthdate) -> None:
        super().__init__(
            "Invalid representative birthdate",
            self.code,
            422,
            f"The legal representative birthdate {birthdate} is invalid or underage.",
            "A data de nascimento do representante é inválida ou ele é menor de idade.",
        )


class IneligibleCnpjStatus(QIException):
    code = "QIT002008"

    def __init__(self, cnpj_status) -> None:
        super().__init__(
            "CNPJ status is not eligible",
            self.code,
            422,
            f"A client with CNPJ status {cnpj_status} cannot be registered.",
            "A situação cadastral do CNPJ não permite o cadastro do cliente.",
        )


class NotFoundAccount(QIException):
    code = "QIT003001"

    def __init__(self, account_key) -> None:
        super().__init__(
            "Account not found",
            self.code,
            404,
            f"Account with key {account_key} was not found.",
            "A conta informada não foi encontrada.",
        )


class ClientAlreadyHasAccount(QIException):
    code = "QIT003002"

    def __init__(self) -> None:
        super().__init__(
            "Client already has an account",
            self.code,
            409,
            "The client already has the account allowed in this version.",
            "O cliente já possui a conta permitida nesta versão.",
        )


class ForbiddenAccountStatusTransition(QIException):
    code = "QIT003003"

    def __init__(self, current_status, new_status) -> None:
        super().__init__(
            "Account status transition not allowed",
            self.code,
            409,
            f"An account with status {current_status} cannot change to {new_status}.",
            "A conta não pode mudar para o status solicitado.",
        )


class AccountWithBalanceCannotBeClosed(QIException):
    code = "QIT003004"

    def __init__(self) -> None:
        super().__init__(
            "Account with balance cannot be closed",
            self.code,
            409,
            "Only an account with zero balance can be closed.",
            "Só é possível encerrar uma conta com saldo zero.",
        )


class InvalidCpf(QIException):
    code = "QIT002009"

    def __init__(self) -> None:
        super().__init__(
            "Invalid CPF",
            self.code,
            422,
            "The CPF is invalid.",
            "O CPF informado não é válido.",
        )


class DuplicatedCpf(QIException):
    code = "QIT002010"

    def __init__(self) -> None:
        super().__init__(
            "CPF already registered",
            self.code,
            409,
            "There is already a client with this CPF.",
            "Já existe um cliente cadastrado com este CPF.",
        )


class InvalidBirthdate(QIException):
    code = "QIT002011"

    def __init__(self, birthdate) -> None:
        super().__init__(
            "Invalid birthdate",
            self.code,
            422,
            f"The birthdate {birthdate} is invalid or underage.",
            "A data de nascimento é inválida ou a pessoa é menor de idade.",
        )


class MissingTariffRule(QIException):
    code = "QIT005001"

    def __init__(self, person_type, transaction_type, direction) -> None:
        super().__init__(
            "Tariff rule not found",
            self.code,
            500,
            f"There is no tariff rule in force for {person_type} {transaction_type} {direction}.",
            "Não há tarifa vigente para esta operação.",
        )


class NotFoundRecipientAccount(QIException):
    code = "QIT004001"

    def __init__(self) -> None:
        super().__init__(
            "Recipient account not found",
            self.code,
            404,
            "No account was found with the informed branch, number and check digit.",
            "A conta de destino informada não foi encontrada.",
        )


class ReusedTransactionReference(QIException):
    code = "QIT004002"

    def __init__(self) -> None:
        super().__init__(
            "Transaction reference reused with different content",
            self.code,
            422,
            "This identification was already used by a transaction with different data.",
            "Esta identificação já foi usada por uma transação com dados diferentes.",
        )


class AccountNotActive(QIException):
    code = "QIT004003"

    def __init__(self) -> None:
        super().__init__(
            "Account is not active",
            self.code,
            422,
            "Only active accounts can send or receive money.",
            "Só contas ativas podem enviar ou receber dinheiro.",
        )


class NotFoundPixKey(QIException):
    code = "QIT004004"

    def __init__(self) -> None:
        super().__init__(
            "Pix key not found",
            self.code,
            404,
            "No account was found for the informed Pix key.",
            "Nenhuma conta foi encontrada para a chave Pix informada.",
        )


class InvalidIdempotencyKey(QIException):
    code = "QIT004005"

    def __init__(self) -> None:
        super().__init__(
            "Invalid idempotency key",
            self.code,
            400,
            "The Idempotency-Key header is required: 1 to 64 letters, digits, '-', '_', '.' or ':'.",
            "O cabeçalho Idempotency-Key é obrigatório: de 1 a 64 letras, números, '-', '_', '.' ou ':'.",
        )


class InsufficientBalance(QIException):
    code = "QIT004006"

    def __init__(self) -> None:
        super().__init__(
            "Insufficient balance",
            self.code,
            422,
            "The account balance does not cover the amount plus the fee.",
            "O saldo da conta não cobre o valor mais a tarifa.",
        )


class TransferToSameAccount(QIException):
    code = "QIT004007"

    def __init__(self) -> None:
        super().__init__(
            "Transfer to the same account",
            self.code,
            422,
            "The recipient account is the same as the sender account.",
            "A conta de destino é a mesma conta de origem.",
        )


class CentralBankRefused(QIException):
    code = "QIT004008"

    def __init__(self) -> None:
        super().__init__(
            "Refused by the Central Bank",
            self.code,
            422,
            "The Central Bank refused the transfer to the other bank. Nothing was changed.",
            "O Banco Central recusou o envio para o outro banco. Nada foi alterado.",
        )


class CentralBankUnavailable(QIException):
    code = "QIT004009"

    def __init__(self) -> None:
        super().__init__(
            "Central Bank unavailable",
            self.code,
            503,
            "The Central Bank did not confirm the transfer in time. Nothing was changed; try again.",
            "O Banco Central não confirmou o envio a tempo. Nada foi alterado; tente de novo.",
        )


class InvalidStatementCursor(QIException):
    code = "QIT006001"

    def __init__(self) -> None:
        super().__init__(
            "Invalid statement cursor",
            self.code,
            422,
            "The cursor does not identify a line of this account statement.",
            "O cursor não identifica uma linha do extrato desta conta.",
        )
