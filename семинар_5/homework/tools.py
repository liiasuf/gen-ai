
from __future__ import annotations

import csv
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date as _date
from datetime import datetime
from pathlib import Path

import sympy  # noqa: F401

DATA_DIR = Path(__file__).resolve().parent / "data"

CBR_FX_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
CBR_KEYIND_URL = "https://www.cbr.ru/key-indicators/"

_TIMEOUT_SEC = 6
_UA = "Mozilla/5.0 (seminar-5-agent)"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as r:
        return r.read()


def _parse_date(s: str | None) -> _date:
    if s is None:
        return _date.today()
    if isinstance(s, _date):
        return s
    # Принимаем "YYYY-MM" как первый день месяца
    if len(s) == 7:
        return datetime.strptime(s + "-01", "%Y-%m-%d").date()
    return datetime.strptime(s, "%Y-%m-%d").date()


# ===========================================================================
# 1. Курс валюты ЦБ
# ===========================================================================

def get_fx_rate(currency: str = "USD", on_date: str | None = None) -> dict:
    """
    Официальный курс валюты к рублю (сколько рублей за 1 единицу валюты).

    Args:
        currency: ISO-код (USD, EUR, CNY, GBP, ...).
        on_date:  YYYY-MM-DD. None → сегодня.

    Returns:
        {"currency": "USD", "date": "2026-04-22", "rate": 82.5, "source": "cbr_live"}
    """
    d = _parse_date(on_date)
    currency = currency.upper()

    try:
        q = urllib.parse.urlencode({"date_req": d.strftime("%d/%m/%Y")})
        xml_bytes = _http_get(f"{CBR_FX_URL}?{q}")
        xml_text = xml_bytes.decode("windows-1251", errors="replace")
        root = ET.fromstring(xml_text)

        for val in root.findall("Valute"):
            if val.findtext("CharCode") == currency:
                nominal = int(val.findtext("Nominal") or 1)
                raw = (val.findtext("Value") or "").replace(",", ".")
                rate = float(raw) / nominal
                return {
                    "currency": currency,
                    "date": d.isoformat(),
                    "rate": round(rate, 4),
                    "source": "cbr_live",
                }

        return _fx_fallback(currency, d, reason=f"Валюты {currency} нет в ответе ЦБ.")

    except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as e:
        return _fx_fallback(
            currency,
            d,
            reason=f"Сбой живого запроса по {currency}. {type(e).__name__}: {e}",
        )


def _fx_fallback(currency: str, d: _date, *, reason: str) -> dict:
    """Ближайшая по дате запись из fx_benchmark.csv."""
    path = DATA_DIR / "fx_benchmark.csv"
    best = None
    best_delta = None

    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["currency"] != currency:
                continue
            row_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            delta = abs((row_date - d).days)
            if best is None or delta < best_delta:
                best = row
                best_delta = delta

    if best is None:
        return {"error": f"нет запасных данных для {currency}"}

    return {
        "currency": currency,
        "date": best["date"],
        "rate": float(best["rate"]),
        "source": "fallback_csv",
        "reason": reason,
    }


# ===========================================================================
# 2. Ключевая ставка ЦБ
# ===========================================================================

_KEY_RATE_RE = re.compile(
    r"Ключевая\s*ставка[^<]*?</\w+>[^<]*?<[^>]*>\s*([\d]{1,2}[.,][\d]{1,2})\s*%",
    re.S | re.I,
)
_KEY_RATE_FALLBACK_RE = re.compile(
    r"Ключевая\s*ставка.{0,200}?(\d{1,2}[.,]\d{1,2})\s*%",
    re.S | re.I,
)


def get_key_rate(on_date: str | None = None) -> dict:
    """
    Ключевая ставка Банка России, действующая на указанную дату, % годовых.

    Returns:
        {"rate": 16.0, "date": "2026-04-22", "valid_from": "2026-03-20", "source": "cbr_live"}
    """
    d = _parse_date(on_date)

    if on_date is None or d == _date.today():
        try:
            html = _http_get(CBR_KEYIND_URL).decode("utf-8", errors="ignore")
            m = _KEY_RATE_RE.search(html) or _KEY_RATE_FALLBACK_RE.search(html)
            if m:
                val = float(m.group(1).replace(",", "."))
                return {"rate": val, "date": d.isoformat(), "source": "cbr_live"}
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass

    path = DATA_DIR / "key_rate_history.csv"
    chosen = None

    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rd = datetime.strptime(row["valid_from"], "%Y-%m-%d").date()
            if rd <= d:
                chosen = row
            else:
                break

    if chosen is None:
        return {"error": f"нет исторической ставки на {d}"}

    return {
        "rate": float(chosen["rate"]),
        "date": d.isoformat(),
        "valid_from": chosen["valid_from"],
        "source": "fallback_csv",
    }


# ===========================================================================
# 3. Инфляция (ИПЦ г/г, Росстат)
# ===========================================================================

def get_inflation(year: int, month: int) -> dict:
    """
    Индекс потребительских цен Росстата, % г/г, на конец месяца.

    Returns:
        {"year": 2024, "month": 3, "cpi_yoy": 7.72, "source": "rosstat_csv"}
    """
    year = int(year)
    month = int(month)

    if not (1 <= month <= 12):
        return {"error": f"month={month} вне промежутка 1..12"}

    path = DATA_DIR / "cpi_ru_monthly.csv"
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["year"]) == year and int(row["month"]) == month:
                return {
                    "year": year,
                    "month": month,
                    "cpi_yoy": float(row["cpi_yoy"]),
                    "source": "rosstat_csv",
                }

    return {"error": f"нет данных ИПЦ на {year}-{month:02d}"}


# ===========================================================================
# 4. Безработица (Росстат)
# ===========================================================================

def get_unemployment(year: int, month: int) -> dict:
    """
    Уровень безработицы (МОТ) Росстата, % от рабочей силы, на конец месяца.

    Returns:
        {"year": 2024, "month": 3, "unemployment": 2.7, "source": "rosstat_csv"}
    """
    year = int(year)
    month = int(month)

    if not (1 <= month <= 12):
        return {"error": f"month={month} вне промежутка 1..12"}

    path = DATA_DIR / "unemployment_ru_monthly.csv"
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["year"]) == year and int(row["month"]) == month:
                return {
                    "year": year,
                    "month": month,
                    "unemployment": float(row["unemployment"]),
                    "source": "rosstat_csv",
                }

    return {"error": f"нет данных по безработице на {year}-{month:02d}"}


# ===========================================================================
# 5. Калькулятор
# ===========================================================================

def calculate(expression: str) -> dict:
    """
    Безопасный математический калькулятор.

    Returns:
        {"expression": "(21 - 9.5)", "result": 11.5}
        {"expression": ..., "error": "..."}
    """
    if not isinstance(expression, str) or not expression.strip():
        return {"error": "пустое выражение"}

    try:
        val = float(sympy.sympify(expression.replace("^", "**")))
        return {"expression": expression, "result": round(val, 6)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ===========================================================================
# 6. Сравнение двух периодов (домашнее задание)
# ===========================================================================

_METRIC_ALIASES = {
    "key_rate":    "key_rate",
    "fx_usd":      "fx_USD",
    "fx_eur":      "fx_EUR",
    "fx_cny":      "fx_CNY",
    "cpi":         "cpi",
    "unemployment":"unemployment",
}


def _get_metric_value(metric: str, period: str) -> tuple[str, float]:
    """
    Вернуть (дата_факт, значение) для метрики в заданном периоде.
    period — "YYYY-MM" или "YYYY-MM-DD".
    """
    d = _parse_date(period)

    if metric == "key_rate":
        res = get_key_rate(d.isoformat())
        if "error" in res:
            raise ValueError(res["error"])
        return res["date"], res["rate"]

    if metric.startswith("fx_"):
        currency = metric.split("_", 1)[1].upper()
        res = get_fx_rate(currency, d.isoformat())
        if "error" in res:
            raise ValueError(res["error"])
        return res["date"], res["rate"]

    if metric == "cpi":
        res = get_inflation(d.year, d.month)
        if "error" in res:
            raise ValueError(res["error"])
        return f"{res['year']}-{res['month']:02d}", res["cpi_yoy"]

    if metric == "unemployment":
        res = get_unemployment(d.year, d.month)
        if "error" in res:
            raise ValueError(res["error"])
        return f"{res['year']}-{res['month']:02d}", res["unemployment"]

    raise ValueError(f"Неизвестная метрика: {metric!r}. "
                     f"Допустимые: {list(_METRIC_ALIASES)}")


def compare_periods(
    metric: str,
    period_a: str,
    period_b: str,
) -> dict:
    """
    Сравнить значение метрики в двух периодах.

    Args:
        metric:   "key_rate" | "fx_USD" | "fx_EUR" | "fx_CNY" | "cpi" | "unemployment"
        period_a: "YYYY-MM" или "YYYY-MM-DD"
        period_b: "YYYY-MM" или "YYYY-MM-DD"

    Returns:
        {
          "metric":  "fx_USD",
          "a":       {"date": "2022-01-04", "value": 74.68},
          "b":       {"date": "2026-04-01", "value": 89.57},
          "delta":   14.89,        # b.value - a.value
          "ratio":   1.1996,       # b.value / a.value
          "source":  "fallback_csv / rosstat_csv"
        }
    """
    # Нормализуем имя метрики (регистронезависимо)
    metric_norm = metric.lower().replace("-", "_")
    metric_norm = _METRIC_ALIASES.get(metric_norm, metric_norm)

    try:
        date_a, val_a = _get_metric_value(metric_norm, period_a)
    except ValueError as e:
        return {"error": f"period_a: {e}"}

    try:
        date_b, val_b = _get_metric_value(metric_norm, period_b)
    except ValueError as e:
        return {"error": f"period_b: {e}"}

    delta = round(val_b - val_a, 6)
    ratio = round(val_b / val_a, 6) if val_a != 0 else None

    # Определяем source по тому, что вернули базовые инструменты
    source_map = {
        "key_rate":    "fallback_csv",
        "fx_USD":      "fallback_csv",
        "fx_EUR":      "fallback_csv",
        "fx_CNY":      "fallback_csv",
        "cpi":         "rosstat_csv",
        "unemployment":"rosstat_csv",
    }
    source = source_map.get(metric_norm, "mixed")

    return {
        "metric": metric_norm,
        "a": {"date": date_a, "value": val_a},
        "b": {"date": date_b, "value": val_b},
        "delta": delta,
        "ratio": ratio,
        "source": source,
    }
