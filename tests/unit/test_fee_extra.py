from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from models import FeeRule
from utils.fee import calculate_fee_cents, month_start_brt

BRT = ZoneInfo("America/Sao_Paulo")

PJ_PIX_RULE = FeeRule(person_type="PJ", transaction_type="PIX_OUT", free_monthly_quota=20, fee_cents=99)


# Casos de fronteira que o test_fee.py não cobre (testes da Lupa).


@pytest.mark.parametrize("transaction_type", ["PIX_IN", "TED_IN"])
def test_receiving_is_free_even_with_a_priced_rule_at_hand(transaction_type):
    # TAR-02: mesmo que quem chama passe uma regra com preço, receber é grátis.
    assert calculate_fee_cents("PJ", transaction_type, 500, PJ_PIX_RULE) == 0


def test_pf_never_pays_even_with_a_priced_rule_at_hand():
    # TAR-01: a regra da PJ nunca vale para PF.
    assert calculate_fee_cents("PF", "PIX_OUT", 500, PJ_PIX_RULE) == 0


def test_rule_without_free_quota_charges_the_first_send():
    rule = FeeRule(person_type="PJ", transaction_type="TED_OUT", free_monthly_quota=0, fee_cents=499)
    assert calculate_fee_cents("PJ", "TED_OUT", 0, rule) == 499


@pytest.mark.parametrize("completed", range(0, 25))
def test_exactly_twenty_free_pix_then_every_one_pays(completed):
    # TAR-03: a fronteira inteira, envio a envio: do 1o ao 20o grátis, do 21o em diante 99.
    expected = 0 if completed < 20 else 99
    assert calculate_fee_cents("PJ", "PIX_OUT", completed, PJ_PIX_RULE) == expected


def test_month_start_ignores_the_offset_of_the_input():
    # 2026-11-01 10:00 em Tóquio (+09:00) = 2026-10-31 22:00 em Brasília.
    tokyo = ZoneInfo("Asia/Tokyo")
    assert month_start_brt(datetime(2026, 11, 1, 10, 0, tzinfo=tokyo)) == datetime(2026, 10, 1, tzinfo=BRT)


def test_one_second_before_and_at_the_turn_of_the_month():
    # TAR-04: a cota recomeça exatamente às 00:00:00 do dia 1o em Brasília (03:00 UTC).
    turn = datetime(2026, 12, 1, 3, 0, tzinfo=timezone.utc)
    assert month_start_brt(turn - timedelta(seconds=1)) == datetime(2026, 11, 1, tzinfo=BRT)
    assert month_start_brt(turn) == datetime(2026, 12, 1, tzinfo=BRT)


def test_leap_february():
    assert month_start_brt(datetime(2028, 2, 29, 23, 59, tzinfo=BRT)) == datetime(2028, 2, 1, tzinfo=BRT)
    assert month_start_brt(datetime(2028, 3, 1, 2, 59, tzinfo=timezone.utc)) == datetime(2028, 2, 1, tzinfo=BRT)


def test_every_instant_of_a_month_maps_to_the_same_start():
    # Varre outubro de 2026 de hora em hora, em UTC: todos caem em 1/10 BRT.
    start = datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)
    instant = start
    while instant < end:
        assert month_start_brt(instant) == datetime(2026, 10, 1, tzinfo=BRT)
        instant += timedelta(hours=1)
