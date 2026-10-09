from datetime import datetime
from zoneinfo import ZoneInfo

from errors import MissingTariffRule

BRASILIA = ZoneInfo("America/Sao_Paulo")

PF = "PF"
IN = "IN"


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
    """Tarifa, em centavos, da operação que está sendo feita agora.

    A regra vigente define a cota e o preço, mas duas garantias não dependem
    dela: PF nunca paga (TAR-01) e receber é sempre grátis (TAR-02). O banco
    de dados também recusa uma regra que cobre nesses casos.

    `completed_this_month` são os envios concluídos ANTES deste, do mesmo
    tipo, no mês de Brasília: o 21º Pix chega com 20. Quem chama já travou a
    conta e contou na mesma transação do banco (TAR-07).
    """
    if rule is None:
        raise MissingTariffRule(person_type, transaction_type, direction)
    if person_type == PF or direction == IN:
        return 0
    if rule.monthly_free_quota is None:
        return 0
    if completed_this_month < rule.monthly_free_quota:
        return 0
    return rule.fee_after_quota_cents
