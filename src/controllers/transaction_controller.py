from controllers.base_controller import BaseController
from dtos import TransactionDTO
from errors import AccountNotActive, NotFoundRecipientAccount, ReusedTransactionReference
from models import Account, Entry, Transaction
from repositories import AccountRepository, TransactionRepository


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
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

        transaction = self.transaction_repository.create_incoming_ted(account, ted_data)
        if transaction is None:
            existing = self.transaction_repository.get_incoming(
                Transaction.TED_IN, ted_data["payer"]["bank_code"], ted_data["external_id"]
            )
            if not self._same_ted(existing, account, ted_data):
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
    def _same_ted(transaction: Transaction, account: Account, ted_data: dict) -> bool:
        payer = ted_data["payer"]
        return (
            transaction.destination_account_id == account.id
            and transaction.amount_cents == ted_data["amount_cents"]
            and transaction.counterparty_name == payer["name"]
            and transaction.counterparty_document == payer["document"]
            and transaction.counterparty_branch == payer["branch"]
            and transaction.counterparty_account_number == payer["account_number"]
        )
