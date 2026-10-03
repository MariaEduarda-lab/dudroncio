from models import Account


class AccountDTO:
    @staticmethod
    def only_key(account: Account) -> dict:
        return {"account_key": account.account_key}

    @staticmethod
    def obj_to_dict(account: Account) -> dict:
        return {
            "account_key": account.account_key,
            "client_key": account.client.client_key,
            "branch": account.branch,
            "account_number": account.account_number,
            "check_digit": account.check_digit,
            "balance_cents": account.balance_cents,
            "created_at": account.created_at.isoformat(),
        }
