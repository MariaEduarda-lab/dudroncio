from errors import QIException


class NotFoundSampleEntity(QIException):
    code = "QIT001001"

    def __init__(self, sample_entity_key) -> None:
        title = "Entity not Found"
        http_status = 404
        description = f"Entity with key {sample_entity_key} was not found."
        translation = f"A entidade com chave {sample_entity_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class SampleEntityFinalStatus(QIException):
    code = "QIT001002"

    def __init__(self, old_status, new_status) -> None:
        title = "Entity cannot change status"
        http_status = 409
        description = f"Entity with status {old_status} cannot update to {new_status}."
        translation = "Essa entidade não pode ser atualizada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    """O CPF tem o formato certo e não existe.

    422, e não 400, de propósito: 400 quer dizer "não consegui ler o seu
    pedido". Aqui a API leu, entendeu, e o valor é que não pode existir —
    os dois últimos dígitos não batem com a conta. A diferença está
    explicada em src/utils/document_number.py.
    """

    code = "QIT001003"

    def __init__(self, document_number) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = f"The document number {document_number} is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedDocumentNumber(QIException):
    """Já existe um cadastro com este CPF.

    409 Conflict: o pedido está correto em si, e o que impede é o que já
    está no banco. É a mesma família do SampleEntityFinalStatus aqui em
    cima — conflito com o que já existe, não erro de quem pediu.
    """

    code = "QIT001004"

    def __init__(self, document_number) -> None:
        title = "Document Number already registered"
        http_status = 409
        description = f"There is already an entity with the document number {document_number}."
        translation = "Já existe um cadastro com este CPF."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedEmail(QIException):
    code = "QIT001005"

    def __init__(self, email) -> None:
        title = "Email already registered"
        http_status = 409
        description = f"There is already an entity with the email {email}."
        translation = "Já existe um cadastro com este e-mail."
        super().__init__(title, self.code, http_status, description, translation)


class UnderageSampleEntity(QIException):
    code = "QIT001006"

    def __init__(self, age, minimum_age) -> None:
        title = "Entity is underage"
        http_status = 422
        description = f"The entity is {age} years old, and the minimum is {minimum_age}."
        translation = f"É preciso ter pelo menos {minimum_age} anos."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidBirthdate(QIException):
    """A data tem o formato certo e não existe no calendário.

    Existe porque o `pattern` do schema sabe contar dígitos, não dias:
    "2025-02-30" e "9999-99-99" passam pelo regex e morrem no
    `date.fromisoformat`. Sem esta classe, esse ValueError virava 500 —
    a API culpando a si mesma por um erro de quem chamou.
    """

    code = "QIT001007"

    def __init__(self, birthdate) -> None:
        title = "Invalid Birthdate"
        http_status = 422
        description = f"The birthdate {birthdate} is not a real date."
        translation = "A data de nascimento informada não existe."
        super().__init__(title, self.code, http_status, description, translation)


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

    def __init__(self, cnpj) -> None:
        super().__init__(
            "Invalid CNPJ",
            self.code,
            422,
            f"The CNPJ {cnpj} is invalid.",
            "O CNPJ informado não é válido.",
        )


class DuplicatedCnpj(QIException):
    code = "QIT002003"

    def __init__(self, cnpj) -> None:
        super().__init__(
            "CNPJ already registered",
            self.code,
            409,
            f"There is already a client with CNPJ {cnpj}.",
            "Já existe um cliente cadastrado com este CNPJ.",
        )


class DuplicatedClientEmail(QIException):
    code = "QIT002004"

    def __init__(self, email) -> None:
        super().__init__(
            "Email already registered",
            self.code,
            409,
            f"There is already a client or representative with email {email}.",
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
