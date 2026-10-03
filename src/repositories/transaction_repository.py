from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import Account, Entry, Transaction

INCOMING_TYPES = [Transaction.TED_IN]


class TransactionRepository:
    """Persistencia de transacoes e lancamentos; as regras ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create_incoming_ted(self, account: Account, ted_data: dict) -> Transaction | None:
        """Grava a TED recebida, ou devolve None se o aviso ja foi gravado.

        O ON CONFLICT faz o indice unico decidir: dois avisos iguais ao
        mesmo tempo nao passam os dois, porque o segundo espera o primeiro
        terminar e entao encontra a linha (TRA-21).
        """
        payer = ted_data["payer"]
        statement = (
            insert(Transaction)
            .values(
                transaction_key=uuid4(),
                type=Transaction.TED_IN,
                amount_cents=ted_data["amount_cents"],
                fee_cents=0,
                destination_account_id=account.id,
                external_id=ted_data["external_id"],
                counterparty_name=payer["name"],
                counterparty_document=payer["document"],
                counterparty_bank_code=payer["bank_code"],
                counterparty_branch=payer["branch"],
                counterparty_account_number=payer["account_number"],
            )
            .on_conflict_do_nothing(
                index_elements=[Transaction.type, Transaction.counterparty_bank_code, Transaction.external_id],
                index_where=Transaction.type.in_(INCOMING_TYPES),
            )
            .returning(Transaction.id)
        )
        transaction_id = self.session.execute(statement).scalar_one_or_none()
        if transaction_id is None:
            return None
        return self.session.get(Transaction, transaction_id)

    def get_incoming(self, transaction_type: str, bank_code: str, external_id: str) -> Transaction | None:
        return (
            self.session.query(Transaction)
            .filter(
                Transaction.type == transaction_type,
                Transaction.counterparty_bank_code == bank_code,
                Transaction.external_id == external_id,
            )
            .first()
        )

    def create_entry(
        self, account_id: int, transaction: Transaction, entry_type: str, amount_cents: int, balance_after_cents: int
    ) -> Entry:
        entry = Entry(
            entry_key=uuid4(),
            account_id=account_id,
            transaction_id=transaction.id,
            entry_type=entry_type,
            amount_cents=amount_cents,
            balance_after_cents=balance_after_cents,
        )
        self.session.add(entry)
        return entry
