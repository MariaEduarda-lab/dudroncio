from datetime import datetime
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from database import Context
from models import Account, AccountMovement, Transaction


class TransactionRepository:
    """Persistencia de transacoes e movimentos de conta; as regras ficam no controller."""

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create_incoming(
        self,
        transaction_type: str,
        account: Account,
        notice: dict,
        tariff_rule_id: int,
        pix_key: str | None = None,
    ) -> Transaction | None:
        """Grava o recebimento (TED ou Pix), ou devolve None se o aviso ja foi gravado.

        O ON CONFLICT faz o indice unico decidir: dois avisos iguais ao
        mesmo tempo nao passam os dois, porque o segundo espera o primeiro
        terminar e entao encontra a linha (TRA-21).
        """
        payer = notice["payer"]
        statement = (
            insert(Transaction)
            .values(
                transaction_key=uuid4(),
                type=transaction_type,
                direction=Transaction.IN,
                amount_cents=notice["amount_cents"],
                fee_cents=0,
                tariff_rule_id=tariff_rule_id,
                destination_account_id=account.id,
                external_reference=notice["external_id"],
                counterparty_name=payer["name"],
                counterparty_document=payer["document"],
                counterparty_bank_code=payer["bank_code"],
                counterparty_branch=payer["branch"],
                counterparty_account_number=payer["account_number"],
                pix_key=pix_key,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    Transaction.type,
                    Transaction.counterparty_bank_code,
                    Transaction.external_reference,
                ],
                index_where=Transaction.direction == Transaction.IN,
            )
            .returning(Transaction.id)
        )
        transaction_id = self.session.execute(statement).scalar_one_or_none()
        if transaction_id is None:
            return None
        return self.session.get(Transaction, transaction_id)

    def create_outgoing(self, transaction_data: dict) -> Transaction | None:
        """Grava o envio, ou devolve None se a chave de idempotencia ja foi usada.

        O ON CONFLICT faz a constraint decidir: dois pedidos com a mesma
        chave ao mesmo tempo nao passam os dois.
        """
        statement = (
            insert(Transaction)
            .values(**{"transaction_key": uuid4(), "direction": Transaction.OUT, **transaction_data})
            .on_conflict_do_nothing(constraint="uq_transaction_idempotency")
            .returning(Transaction.id)
        )
        transaction_id = self.session.execute(statement).scalar_one_or_none()
        if transaction_id is None:
            return None
        return self.session.get(Transaction, transaction_id)

    def get_by_idempotency_key(self, source_account_id: int, idempotency_key: str) -> Transaction | None:
        return (
            self.session.query(Transaction)
            .filter(
                Transaction.source_account_id == source_account_id,
                Transaction.idempotency_key == idempotency_key,
            )
            .first()
        )

    def count_completed_sends(self, account_id: int, transaction_type: str, since: datetime) -> int:
        """Envios de um tipo desde `since`. Recusas nao viram linha (TRA-09).

        Quem chama ja travou a conta: dois envios simultaneos nao contam o
        mesmo numero (TAR-07).
        """
        return (
            self.session.query(func.count(Transaction.id))
            .filter(
                Transaction.source_account_id == account_id,
                Transaction.type == transaction_type,
                Transaction.direction == Transaction.OUT,
                Transaction.created_at >= since,
            )
            .scalar()
        )

    def get_incoming(self, transaction_type: str, bank_code: str, external_reference: str) -> Transaction | None:
        return (
            self.session.query(Transaction)
            .filter(
                Transaction.type == transaction_type,
                Transaction.direction == Transaction.IN,
                Transaction.counterparty_bank_code == bank_code,
                Transaction.external_reference == external_reference,
            )
            .first()
        )

    def create_movement(
        self,
        account_id: int,
        transaction: Transaction,
        direction: str,
        movement_type: str,
        amount_cents: int,
        balance_after_cents: int,
    ) -> AccountMovement:
        movement = AccountMovement(
            movement_key=uuid4(),
            account_id=account_id,
            transaction_id=transaction.id,
            direction=direction,
            movement_type=movement_type,
            amount_cents=amount_cents,
            balance_after_cents=balance_after_cents,
        )
        self.session.add(movement)
        return movement
