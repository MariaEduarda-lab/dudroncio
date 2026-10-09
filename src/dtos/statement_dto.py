from zoneinfo import ZoneInfo

from models import AccountMovement, Client, Transaction

# O extrato e lido pelo cliente: data e hora no horario de Brasilia.
BRASILIA = ZoneInfo("America/Sao_Paulo")


class StatementDTO:
    @staticmethod
    def page_to_dict(movements: list[AccountMovement], next_cursor: str | None) -> dict:
        return {
            "movements": [StatementDTO.movement_to_dict(movement) for movement in movements],
            "next_cursor": next_cursor,
        }

    @staticmethod
    def movement_to_dict(movement: AccountMovement) -> dict:
        transaction = movement.transaction
        method = "Pix" if transaction.type == Transaction.PIX else "TED"
        counterparty_name = None

        if movement.movement_type == AccountMovement.FEE:
            description = f"Tarifa de {method}"
        else:
            counterparty_name = StatementDTO._counterparty_name(movement, transaction)
            if movement.direction == AccountMovement.CREDIT:
                received = "recebido" if method == "Pix" else "recebida"
                description = f"{method} {received} de {counterparty_name}"
            else:
                description = f"{method} para {counterparty_name}"

        return {
            "movement_key": str(movement.movement_key),
            "created_at": movement.created_at.astimezone(BRASILIA).isoformat(),
            "direction": movement.direction,
            "movement_type": movement.movement_type,
            "description": description,
            # No banco o valor e positivo e a direcao evita ambiguidade.
            # No extrato, debitos aparecem com sinal negativo para leitura.
            "amount_cents": StatementDTO._signed_amount(movement),
            "balance_after_cents": movement.balance_after_cents,
            "transaction_key": str(transaction.transaction_key),
            "counterparty_name": counterparty_name,
        }

    @staticmethod
    def _counterparty_name(movement: AccountMovement, transaction: Transaction) -> str:
        """So o nome da outra parte aparece (EXT-10).

        A transacao guarda a outra parte do ponto de vista de quem a
        originou: quem pagou num recebimento, quem recebeu num envio. No
        envio entre clientes nossos, o credito e do recebedor, e para ele a
        outra parte e quem enviou.
        """
        if transaction.direction == Transaction.IN or movement.direction == AccountMovement.DEBIT:
            return transaction.counterparty_name
        sender = transaction.source_account.client
        return sender.full_name if sender.person_type == Client.PF else sender.legal_name

    @staticmethod
    def _signed_amount(movement: AccountMovement) -> int:
        if movement.direction == AccountMovement.DEBIT:
            return -movement.amount_cents
        return movement.amount_cents
