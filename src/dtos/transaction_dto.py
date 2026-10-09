from models import Transaction
from utils.document_number import masked_document


class TransactionDTO:
    @staticmethod
    def obj_to_dict(transaction: Transaction) -> dict:
        response = {
            "transaction_key": str(transaction.transaction_key),
            "type": transaction.type,
            "direction": transaction.direction,
            "amount_cents": transaction.amount_cents,
            "fee_cents": transaction.fee_cents,
            "created_at": transaction.created_at.isoformat(),
        }

        if transaction.direction == Transaction.OUT:
            response["account_key"] = str(transaction.source_account.account_key)
            response["recipient"] = {
                "name": transaction.counterparty_name,
                "document": masked_document(transaction.counterparty_document),
                "bank_code": transaction.counterparty_bank_code,
                "branch": transaction.counterparty_branch,
                "account_number": transaction.counterparty_account_number,
            }
        else:
            response["account_key"] = str(transaction.destination_account.account_key)
            response["payer"] = {
                "name": transaction.counterparty_name,
                "document": transaction.counterparty_document,
                "bank_code": transaction.counterparty_bank_code,
                "branch": transaction.counterparty_branch,
                "account_number": transaction.counterparty_account_number,
            }

        if transaction.type == Transaction.PIX:
            response["pix_key"] = transaction.pix_key
        return response
