from zoneinfo import ZoneInfo

from models import Client, Entry, Transaction

# O extrato e lido pelo cliente: data e hora no horario de Brasilia.
BRASILIA = ZoneInfo("America/Sao_Paulo")

PIX_TYPES = (Transaction.PIX_IN, Transaction.PIX_OUT)
RECEIVED_TYPES = (Transaction.PIX_IN, Transaction.TED_IN)


class StatementDTO:
    @staticmethod
    def page_to_dict(entries: list[Entry], next_cursor: str | None) -> dict:
        return {
            "entries": [StatementDTO.entry_to_dict(entry) for entry in entries],
            "next_cursor": next_cursor,
        }

    @staticmethod
    def entry_to_dict(entry: Entry) -> dict:
        transaction = entry.transaction
        method = "Pix" if transaction.type in PIX_TYPES else "TED"
        counterparty_name = None

        if entry.entry_type == Entry.FEE:
            description = f"Tarifa de {method}"
        else:
            counterparty_name = StatementDTO._counterparty_name(entry, transaction)
            if entry.amount_cents > 0:
                received = "recebido" if method == "Pix" else "recebida"
                description = f"{method} {received} de {counterparty_name}"
            else:
                description = f"{method} para {counterparty_name}"

        return {
            "entry_key": str(entry.entry_key),
            "created_at": entry.created_at.astimezone(BRASILIA).isoformat(),
            "type": entry.entry_type,
            "description": description,
            "amount_cents": entry.amount_cents,
            "balance_after_cents": entry.balance_after_cents,
            "transaction_key": str(transaction.transaction_key),
            "counterparty_name": counterparty_name,
        }

    @staticmethod
    def _counterparty_name(entry: Entry, transaction: Transaction) -> str:
        """So o nome da outra parte aparece (EXT-10).

        A transacao guarda a outra parte do ponto de vista de quem a
        originou: quem pagou num recebimento, quem recebeu num envio. No
        envio entre clientes nossos, a linha de credito e do recebedor, e
        para ele a outra parte e quem enviou.
        """
        if transaction.type in RECEIVED_TYPES or entry.amount_cents < 0:
            return transaction.counterparty_name
        sender = transaction.source_account.client
        return sender.full_name if sender.person_type == Client.PF else sender.legal_name
