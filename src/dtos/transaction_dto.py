from models import Transaction


class TransactionDTO:
    @staticmethod
    def obj_to_dict(transaction: Transaction) -> dict:
        response = {
            "transaction_key": str(transaction.transaction_key),
            "type": transaction.type,
            "amount_cents": transaction.amount_cents,
            "fee_cents": transaction.fee_cents,
            "account_key": str(transaction.destination_account.account_key),
            "payer": {
                "name": transaction.counterparty_name,
                "document": transaction.counterparty_document,
                "bank_code": transaction.counterparty_bank_code,
                "branch": transaction.counterparty_branch,
                "account_number": transaction.counterparty_account_number,
            },
            "created_at": transaction.created_at.isoformat(),
        }
        if transaction.type == Transaction.PIX_IN:
            response["pix_key"] = transaction.pix_key
        return response
