from controllers.base_controller import BaseController
from dtos import TransactionDTO
from errors import AccountNotActive, NotFoundPixKey, NotFoundRecipientAccount, ReusedTransactionReference
from models import Account, Entry, Transaction
from repositories import AccountRepository, ClientRepository, TransactionRepository
from utils.pix_key import normalize_pix_key


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.client_repository = ClientRepository(self.context)
        self.transaction_repository = TransactionRepository(self.context)

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
