from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from errors import MissingFeeRule
from models import FeeRule
from utils.fee import calculate_fee_cents, month_start_brt

BRT = ZoneInfo("America/Sao_Paulo")

PJ_PIX_RULE = FeeRule(person_type="PJ", transaction_type="PIX_OUT", free_monthly_quota=20, fee_cents=99)
PJ_TED_RULE = FeeRule(person_type="PJ", transaction_type="TED_OUT", free_monthly_quota=2, fee_cents=499)


# completed_sends_this_month conta os envios concluidos ANTES deste: o 20o
# Pix do mes chega com 19 ja concluidos.


@pytest.mark.parametrize("transaction_type", ["PIX_OUT", "TED_OUT", "PIX_IN", "TED_IN"])
def test_pf_never_pays(transaction_type):
    # TAR-01: Ana (PF) faz o 30o Pix do mes e nao paga.
    assert calculate_fee_cents("PF", transaction_type, 29, None) == 0


@pytest.mark.parametrize("transaction_type", ["PIX_IN", "TED_IN"])
def test_receiving_is_always_free(transaction_type):
    # TAR-02: a distribuidora recebe 100 Pix no mes, todos gratis.
    assert calculate_fee_cents("PJ", transaction_type, 100, None) == 0


def test_twentieth_pix_is_free():
    assert calculate_fee_cents("PJ", "PIX_OUT", 19, PJ_PIX_RULE) == 0


def test_twenty_first_pix_pays_99_cents():
    assert calculate_fee_cents("PJ", "PIX_OUT", 20, PJ_PIX_RULE) == 99


def test_first_pix_of_the_month_is_free():
    assert calculate_fee_cents("PJ", "PIX_OUT", 0, PJ_PIX_RULE) == 0


def test_every_pix_after_the_quota_pays():
    assert calculate_fee_cents("PJ", "PIX_OUT", 57, PJ_PIX_RULE) == 99


def test_second_ted_is_free():
    assert calculate_fee_cents("PJ", "TED_OUT", 1, PJ_TED_RULE) == 0


def test_third_ted_pays_499_cents():
    assert calculate_fee_cents("PJ", "TED_OUT", 2, PJ_TED_RULE) == 499


def test_price_comes_from_the_rule():
    # TAR-14: um preco novo e so outra regra; o calculo nao fixa valores.
    new_rule = FeeRule(person_type="PJ", transaction_type="PIX_OUT", free_monthly_quota=5, fee_cents=150)
    assert calculate_fee_cents("PJ", "PIX_OUT", 4, new_rule) == 0
    assert calculate_fee_cents("PJ", "PIX_OUT", 5, new_rule) == 150


@pytest.mark.parametrize("transaction_type", ["PIX_OUT", "TED_OUT"])
def test_pj_send_without_rule_is_an_error(transaction_type):
    # Sem regra vigente o banco nao sabe o preco: nunca cobrar zero por engano.
    with pytest.raises(MissingFeeRule):
        calculate_fee_cents("PJ", transaction_type, 0, None)


def test_month_start_is_first_day_midnight_in_brasilia():
    start = month_start_brt(datetime(2026, 10, 15, 14, 0, tzinfo=BRT))
    assert start == datetime(2026, 10, 1, 0, 0, tzinfo=BRT)
    assert start.utcoffset() is not None


def test_last_minutes_of_the_month_in_brasilia_are_still_that_month():
    start = month_start_brt(datetime(2026, 10, 31, 23, 30, tzinfo=BRT))
    assert start == datetime(2026, 10, 1, 0, 0, tzinfo=BRT)


def test_midnight_of_day_one_in_brasilia_starts_the_new_month():
    start = month_start_brt(datetime(2026, 11, 1, 0, 0, tzinfo=BRT))
    assert start == datetime(2026, 11, 1, 0, 0, tzinfo=BRT)


def test_utc_already_in_the_next_month_is_still_previous_month_in_brasilia():
    # 2026-11-01 02:00 UTC = 2026-10-31 23:00 em Brasilia.
    start = month_start_brt(datetime(2026, 11, 1, 2, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 10, 1, 0, 0, tzinfo=BRT)


def test_month_start_in_utc_is_three_in_the_morning():
    start = month_start_brt(datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc))
    assert start.astimezone(timezone.utc) == datetime(2026, 10, 1, 3, 0, tzinfo=timezone.utc)


def test_year_turn_in_brasilia():
    # 2027-01-01 01:00 UTC = 2026-12-31 22:00 em Brasilia.
    assert month_start_brt(datetime(2027, 1, 1, 1, 0, tzinfo=timezone.utc)) == datetime(2026, 12, 1, tzinfo=BRT)
    assert month_start_brt(datetime(2027, 1, 1, 3, 0, tzinfo=timezone.utc)) == datetime(2027, 1, 1, tzinfo=BRT)


def test_naive_datetime_is_rejected():
    # Sem fuso nao da para saber em que mes de Brasilia o instante cai.
    with pytest.raises(ValueError):
        month_start_brt(datetime(2026, 10, 31, 23, 30))
