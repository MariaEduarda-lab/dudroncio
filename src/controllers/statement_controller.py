from controllers.base_controller import BaseController
from dtos import StatementDTO
from errors import InvalidStatementCursor, NotFoundAccount
from repositories import AccountRepository, EntryRepository

DEFAULT_PAGE_SIZE = 50


class StatementController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.entry_repository = EntryRepository(self.context)

    def get(self, account_key: str, limit: int | None, after: str | None) -> dict:
        """Uma pagina do extrato, do lancamento mais recente para o mais antigo."""
        account = self.account_repository.get_by_key(account_key)
        if account is None:
            raise NotFoundAccount(account_key)

        before_entry_id = None
        if after is not None:
            cursor = self.entry_repository.get_by_key(after)
            # Cursor de outra conta e recusado como se nao existisse (EXT-16).
            if cursor is None or cursor.account_id != account.id:
                raise InvalidStatementCursor()
            before_entry_id = cursor.id

        page_size = limit or DEFAULT_PAGE_SIZE
        # Uma linha a mais so para saber se ha proxima pagina.
        entries = self.entry_repository.list_for_statement(account.id, before_entry_id, page_size + 1)
        has_next = len(entries) > page_size
        entries = entries[:page_size]
        next_cursor = str(entries[-1].entry_key) if has_next else None
        return StatementDTO.page_to_dict(entries, next_cursor)
