import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from connectors import CentralBankConnector
from constants import OUR_BANK_CODE
from controllers.base_controller import BaseController
from dtos import TransactionDTO
from errors import (
    AccountNotActive,
    CentralBankRefused,
    CentralBankUnavailable,
    InsufficientBalance,
    InvalidIdempotencyKey,
    NotFoundAccount,
    NotFoundPixKey,
    NotFoundRecipientAccount,
    ReusedTransactionReference,
    TransferToSameAccount,
)
from models import Account, Client, Entry, Transaction
from repositories import AccountRepository, ClientRepository, FeeRepository, TransactionRepository
from utils.fee import calculate_fee_cents, month_start_brt
from utils.pix_key import normalize_pix_key
from utils.schema_handler import matches_schema

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
SEND_TYPES = {"PIX": Transaction.PIX_OUT, "TED": Transaction.TED_OUT}
CONFIRMATION_SCHEMA = "central_bank_confirmation.json"


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.client_repository = ClientRepository(self.context)
        self.fee_repository = FeeRepository(self.context)
        self.central_bank_connector = CentralBankConnector()
        self.transaction_repository = TransactionRepository(self.context)

    def send(self, account_key: str, send_data: dict, idempotency_key: str | None) -> tuple[dict, bool]:
        """Envia Pix ou TED. Devolve a transacao e se ela foi criada agora.

        O pedido repetido (mesma chave de idempotencia) devolve a transacao
        que ja existe. Destino nosso: liquidado aqui dentro. Destino em
        outro banco: so acontece se o Banco Central confirmar. Qualquer
        recusa desfaz tudo e deixa a chave livre para uma nova tentativa.
        """
        if idempotency_key is None or not IDEMPOTENCY_KEY_PATTERN.match(idempotency_key):
            raise InvalidIdempotencyKey()

        source = self.account_repository.get_by_key(account_key)
        if source is None:
            raise NotFoundAccount(account_key)

        request = self._normalized_send(send_data)
        request_hash = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        outgoing = {
            "type": SEND_TYPES[send_data["type"]],
            "amount_cents": request["amount_cents"],
            "source_account_id": source.id,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "pix_key": request.get("pix_key"),
        }

        # Pedido repetido devolve a transacao que ja existe, mesmo que o
        # destino tenha mudado de estado depois (TRA-12).
        existing = self.transaction_repository.get_by_idempotency_key(source.id, idempotency_key)
        if existing is not None:
            return self._repeated_send(existing, request_hash)

        destination = self._find_our_destination(request)
        if destination is None:
            return self._send_to_other_bank(source, request, outgoing)
        return self._send_to_our_client(source, destination, outgoing)

    def _send_to_our_client(self, source: Account, destination: Account, outgoing: dict) -> tuple[dict, bool]:
        """Liquidado aqui dentro, sem Banco Central (TRA-16)."""
        if destination.id == source.id:
            raise TransferToSameAccount()

        self.account_repository.lock_by_ids([source.id, destination.id])
        if source.status != Account.ACTIVE or destination.status != Account.ACTIVE:
            self.session.rollback()
            raise AccountNotActive()

        fee_cents, fee_rule_id = self._fee_for(source, outgoing["type"])
        transaction = self.transaction_repository.create_outgoing(
            {
                **outgoing,
                "fee_cents": fee_cents,
                "fee_rule_id": fee_rule_id,
                "destination_account_id": destination.id,
                **self._counterparty_of(destination),
            }
        )
        if transaction is None:
            return self._repeated_after_wait(source, outgoing)

        self._debit_with_entries(source, transaction)

        # A tarifa ainda nao entra em conta nenhuma: a conta do banco esta adiada.
        destination_balance = self.account_repository.credit(destination.id, transaction.amount_cents)
        self.transaction_repository.create_entry(
            destination.id, transaction, Entry.VALUE, transaction.amount_cents, destination_balance
        )
        return self._commit_created(transaction)

    def _send_to_other_bank(self, source: Account, request: dict, outgoing: dict) -> tuple[dict, bool]:
        """Pergunta ao Banco Central com a conta travada e o valor ja debitado.

        Sem saldo, nem chega a perguntar. Se ele nao confirma, o rollback
        devolve o debito: nada foi registrado e a chave segue livre (TRA-18).
        """
        self.account_repository.lock_by_ids([source.id])
        if source.status != Account.ACTIVE:
            self.session.rollback()
            raise AccountNotActive()

        fee_cents, fee_rule_id = self._fee_for(source, outgoing["type"])
        balance_after = self.account_repository.debit(source.id, outgoing["amount_cents"] + fee_cents)
        if balance_after is None:
            self.session.rollback()
            raise InsufficientBalance()

        transaction_key = uuid4()
        recipient = self._ask_central_bank(str(transaction_key), source, request)
        transaction = self.transaction_repository.create_outgoing(
            {
                **outgoing,
                "transaction_key": transaction_key,
                "fee_cents": fee_cents,
                "fee_rule_id": fee_rule_id,
                "counterparty_name": recipient["name"],
                "counterparty_document": recipient["document"],
                "counterparty_bank_code": recipient["bank_code"],
                "counterparty_branch": recipient["branch"],
                "counterparty_account_number": recipient["account_number"],
            }
        )
        if transaction is None:
            return self._repeated_after_wait(source, outgoing)

        self._create_debit_entries(source, transaction, balance_after)
        return self._commit_created(transaction)

    def _ask_central_bank(self, transaction_key: str, source: Account, request: dict) -> dict:
        """Dados do recebedor no outro banco, se o Banco Central confirmou o envio."""
        payer = {key.removeprefix("counterparty_"): value for key, value in self._counterparty_of(source).items()}
        if "pix_key" in request:
            response = self.central_bank_connector.send_pix(
                transaction_key, request["amount_cents"], request["pix_key"], payer
            )
            not_found = NotFoundPixKey
        else:
            response = self.central_bank_connector.send_ted(
                transaction_key, request["amount_cents"], request["recipient"], payer
            )
            not_found = NotFoundRecipientAccount

        if response is not None and response.status == 200 and matches_schema(response.json, CONFIRMATION_SCHEMA):
            return response.json["recipient"]

        self.session.rollback()
        if response is not None and response.status == 404:
            raise not_found()
        if response is not None and 400 <= response.status < 500:
            raise CentralBankRefused()
        # Erro dele, tempo esgotado ou resposta sem sentido: na duvida, o
        # banco nao age as cegas.
        raise CentralBankUnavailable()

    def _repeated_after_wait(self, source: Account, outgoing: dict) -> tuple[dict, bool]:
        # Outro pedido com a mesma chave terminou enquanto este esperava a trava.
        self.session.rollback()
        existing = self.transaction_repository.get_by_idempotency_key(source.id, outgoing["idempotency_key"])
        return self._repeated_send(existing, outgoing["request_hash"])

    def _debit_with_entries(self, source: Account, transaction: Transaction) -> None:
        balance_after = self.account_repository.debit(source.id, transaction.amount_cents + transaction.fee_cents)
        if balance_after is None:
            self.session.rollback()
            raise InsufficientBalance()
        self._create_debit_entries(source, transaction, balance_after)

    def _create_debit_entries(self, source: Account, transaction: Transaction, balance_after: int) -> None:
        # Um UPDATE so na origem (valor + tarifa) e dois lancamentos: o do
        # valor com o saldo antes da tarifa, o da tarifa com o saldo final.
        self.transaction_repository.create_entry(
            source.id, transaction, Entry.VALUE, -transaction.amount_cents, balance_after + transaction.fee_cents
        )
        if transaction.fee_cents > 0:
            self.transaction_repository.create_entry(
                source.id, transaction, Entry.FEE, -transaction.fee_cents, balance_after
            )

    def _commit_created(self, transaction: Transaction) -> tuple[dict, bool]:
        self.session.flush()
        response = TransactionDTO.obj_to_dict(transaction)
        self.session.commit()
        return response, True

    @staticmethod
    def _counterparty_of(account: Account) -> dict:
        """Dados de uma conta nossa como outra parte de uma transacao."""
        client = account.client
        return {
            "counterparty_name": client.full_name if client.person_type == Client.PF else client.legal_name,
            "counterparty_document": client.document_number,
            "counterparty_bank_code": OUR_BANK_CODE,
            "counterparty_branch": account.branch,
            "counterparty_account_number": f"{account.account_number}-{account.check_digit}",
        }

    def receive_ted(self, ted_data: dict) -> tuple[dict, bool]:
        """Credita uma TED que chegou de outro banco, avisada pelo Banco Central.

        Devolve a transacao e se ela foi criada agora. Um aviso repetido
        devolve a transacao que ja existia, sem creditar de novo.
        """
        recipient = ted_data["recipient"]
        account = self.account_repository.get_by_number(
            recipient["branch"], recipient["account_number"], recipient["check_digit"]
        )
        if account is None:
            raise NotFoundRecipientAccount()

        return self._receive(Transaction.TED_IN, account, ted_data)

    def receive_pix(self, pix_data: dict) -> tuple[dict, bool]:
        """Credita um Pix que chegou de outro banco, encontrando a conta pela chave.

        A chave e guardada normalizada: o mesmo aviso com a chave escrita de
        outro jeito (com mascara, em maiusculas) continua sendo o mesmo Pix.
        """
        pix_key = normalize_pix_key(pix_data["pix_key"])
        client = self.client_repository.get_by_pix_key(pix_key)
        if client is None or client.account is None:
            raise NotFoundPixKey()

        return self._receive(Transaction.PIX_IN, client.account, pix_data, pix_key)

    @staticmethod
    def _normalized_send(send_data: dict) -> dict:
        """O pedido como ele e comparado: chave Pix normalizada, sem campos extras."""
        request = {"type": send_data["type"], "amount_cents": send_data["amount_cents"]}
        if send_data["type"] == "PIX":
            request["pix_key"] = normalize_pix_key(send_data["pix_key"])
        else:
            request["recipient"] = dict(send_data["recipient"])
        return request

    def _find_our_destination(self, request: dict) -> Account | None:
        """Conta de destino no nosso banco, ou None se o destino e outro banco.

        Chave Pix de um cliente nosso, ou TED com o nosso codigo: o envio e
        interno. Se parece nosso mas nao existe (cliente sem conta, conta
        999 inexistente), o pedido e recusado aqui mesmo.
        """
        if "pix_key" in request:
            client = self.client_repository.get_by_pix_key(request["pix_key"])
            if client is None:
                return None
            if client.account is None:
                raise NotFoundPixKey()
            return client.account

        recipient = request["recipient"]
        if recipient["bank_code"] != OUR_BANK_CODE:
            return None
        account = self.account_repository.get_by_number(
            recipient["branch"], recipient["account_number"], recipient["check_digit"]
        )
        if account is None:
            raise NotFoundRecipientAccount()
        return account

    def _fee_for(self, source: Account, transaction_type: str) -> tuple[int, int | None]:
        """Tarifa do envio, contada com a conta de origem ja travada (TAR-07)."""
        now = datetime.now(timezone.utc)
        person_type = source.client.person_type
        rule = self.fee_repository.get_current_rule(person_type, transaction_type, now)
        sends_this_month = self.transaction_repository.count_completed_sends(
            source.id, transaction_type, month_start_brt(now)
        )
        fee_cents = calculate_fee_cents(person_type, transaction_type, sends_this_month, rule)
        return fee_cents, rule.id if rule is not None else None

    def _repeated_send(self, existing: Transaction, request_hash: str) -> tuple[dict, bool]:
        if existing.request_hash != request_hash:
            self.session.rollback()
            raise ReusedTransactionReference()
        response = TransactionDTO.obj_to_dict(existing)
        self.session.rollback()
        return response, False

    def _receive(
        self, transaction_type: str, account: Account, notice: dict, pix_key: str | None = None
    ) -> tuple[dict, bool]:
        transaction = self.transaction_repository.create_incoming(transaction_type, account, notice, pix_key)
        if transaction is None:
            existing = self.transaction_repository.get_incoming(
                transaction_type, notice["payer"]["bank_code"], notice["external_id"]
            )
            if not self._same_notice(existing, account, notice, pix_key):
                self.session.rollback()
                raise ReusedTransactionReference()
            response = TransactionDTO.obj_to_dict(existing)
            self.session.rollback()
            return response, False

        # O lancamento so nasce depois do UPDATE da conta, com o saldo que
        # o proprio UPDATE devolveu.
        balance_after = self.account_repository.credit(account.id, transaction.amount_cents)
        if balance_after is None:
            # Recusar e "nao aconteceu": o rollback desfaz a transacao
            # gravada acima, e o mesmo aviso pode ser reenviado (TRA-14).
            self.session.rollback()
            raise AccountNotActive()

        self.transaction_repository.create_entry(
            account.id, transaction, Entry.VALUE, transaction.amount_cents, balance_after
        )
        self.session.flush()

        response = TransactionDTO.obj_to_dict(transaction)
        self.session.commit()
        return response, True

    @staticmethod
    def _same_notice(transaction: Transaction, account: Account, notice: dict, pix_key: str | None) -> bool:
        payer = notice["payer"]
        return (
            transaction.destination_account_id == account.id
            and transaction.amount_cents == notice["amount_cents"]
            and transaction.pix_key == pix_key
            and transaction.counterparty_name == payer["name"]
            and transaction.counterparty_document == payer["document"]
            and transaction.counterparty_branch == payer["branch"]
            and transaction.counterparty_account_number == payer["account_number"]
        )
