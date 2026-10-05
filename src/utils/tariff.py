from datetime import datetime
from zoneinfo import ZoneInfo

from errors import MissingTariffRule

BRASILIA = ZoneInfo("America/Sao_Paulo")


def month_start_brt(at: datetime) -> datetime:
    """Primeiro instante do mês-calendário de Brasília que contém ``at``."""
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("month_start_brt precisa de um datetime com fuso")

    local = at.astimezone(BRASILIA)
    return datetime(local.year, local.month, 1, tzinfo=BRASILIA)


def calculate_tariff_cents(
    person_type: str,
    transaction_type: str,
    direction: str,
    completed_this_month: int,
    rule,
) -> int:
    """Calcula a tarifa usando exclusivamente a regra explícita vigente."""
    if rule is None:
        raise MissingTariffRule(person_type, transaction_type, direction)
    if rule.monthly_free_quota is None:
        return 0
    if completed_this_month < rule.monthly_free_quota:
        return 0
    return rule.fee_after_quota_cents
