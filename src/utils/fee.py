from datetime import datetime
from zoneinfo import ZoneInfo

from errors import MissingFeeRule

BRASILIA = ZoneInfo("America/Sao_Paulo")

PIX_OUT = "PIX_OUT"
TED_OUT = "TED_OUT"
PIX_IN = "PIX_IN"
TED_IN = "TED_IN"
RECEIVING_TYPES = (PIX_IN, TED_IN)

PF = "PF"


def month_start_brt(at: datetime) -> datetime:
    """Dia 1o, 00:00 em Brasilia, do mes em que `at` cai no horario de Brasilia.

    A cota recomeca no mes-calendario de Brasilia (TAR-04): 23:30 do dia 31
    em Brasilia ainda e o mes que termina, mesmo que em UTC ja seja dia 1o.
    """
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("month_start_brt precisa de um datetime com fuso")

    local = at.astimezone(BRASILIA)
    return datetime(local.year, local.month, 1, tzinfo=BRASILIA)


def calculate_fee_cents(person_type: str, transaction_type: str, completed_sends_this_month: int, rule) -> int:
    """Tarifa, em centavos, do envio que esta sendo feito agora.

    `completed_sends_this_month` sao os envios concluidos antes deste, do
    mesmo tipo, no mes de Brasilia: o 21o Pix chega com 20. Quem chama ja
    travou a conta e contou na mesma transacao do banco (TAR-07).
    """
    if person_type == PF:
        return 0
    if transaction_type in RECEIVING_TYPES:
        return 0
    if rule is None:
        raise MissingFeeRule(person_type, transaction_type)
    if completed_sends_this_month < rule.free_monthly_quota:
        return 0
    return rule.fee_cents
