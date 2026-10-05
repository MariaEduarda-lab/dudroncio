from controllers.base_controller import BaseController
from dtos import StatementDTO
from errors import InvalidStatementCursor, NotFoundAccount
from repositories import AccountMovementRepository, AccountRepository

DEFAULT_PAGE_SIZE = 50


class StatementController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.account_movement_repository = AccountMovementRepository(self.context)

    def get(self, account_key: str, limit: int | None, after: str | None) -> dict:
        """Uma pagina do extrato, do lancamento mais recente para o mais antigo."""
        account = self.account_repository.get_by_key(account_key)
        if account is None:
            raise NotFoundAccount(account_key)

        before_movement_id = None
        if after is not None:
            cursor = self.account_movement_repository.get_by_key(after)
            # Cursor de outra conta e recusado como se nao existisse (EXT-16).
            if cursor is None or cursor.account_id != account.id:
                raise InvalidStatementCursor()
            before_movement_id = cursor.id

        page_size = limit or DEFAULT_PAGE_SIZE
        movements = self.account_movement_repository.list_for_statement(
            account.id, before_movement_id, page_size + 1
        )
        has_next = len(movements) > page_size
        movements = movements[:page_size]
        next_cursor = str(movements[-1].movement_key) if has_next else None
        return StatementDTO.page_to_dict(movements, next_cursor)
