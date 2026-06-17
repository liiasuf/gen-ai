"""
Мини-оценка агента: 10 вопросов (задание 3).

Оригинальные 4 вопроса из стартера + 6 новых:
  - 2 требуют compare_periods (Q5, Q6)
  - 2 «трудных» (Q7, Q8)
  - 2 реальных макро-вопроса (Q9, Q10)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import CACHE_STATS, run_agent

CASES = [
    # ── Исходные 4 вопроса ────────────────────────────────────────────────
    {
        "id": 1,
        "query": "Какая сегодня ключевая ставка ЦБ?",
        "expected_tools": ["get_key_rate"],
        "must_have": [],
        "comment": "Базовый тест — один инструмент, одно число.",
    },
    {
        "id": 2,
        "query": "Сколько стоит доллар сегодня и сколько стоил 1 января 2022?",
        "expected_tools": ["get_fx_rate"],
        "must_have": [],
        "comment": "Два вызова одного инструмента с разными аргументами.",
    },
    {
        "id": 3,
        "query": "Какая сейчас реальная ключевая ставка? (номинальная минус инфляция г/г)",
        "expected_tools": ["get_key_rate", "get_inflation", "calculate"],
        "must_have": ["%"],
        "comment": "Три разных инструмента + арифметика. Классический многостадийный кейс.",
    },
    {
        "id": 4,
        "query": (
            "Посчитай, за сколько лет удвоится вклад 100 тыс руб "
            "при текущей ключевой ставке (формула 72)."
        ),
        "expected_tools": ["get_key_rate", "calculate"],
        "must_have": ["год"],
        "comment": "Вычисление с формулой: 72 / ставка = годы.",
    },

    # ── Вопросы, требующие compare_periods (Q5, Q6) ───────────────────────
    {
        "id": 5,
        "query": "Во сколько раз вырос курс USD с января 2022 по апрель 2026?",
        "expected_tools": ["compare_periods"],
        "must_have": ["раз"],
        "comment": (
            "Вопрос «во сколько раз» — прямое попадание в compare_periods. "
            "Агент должен использовать metric=fx_USD, а не два вызова get_fx_rate."
        ),
    },
    {
        "id": 6,
        "query": (
            "Как изменилась инфляция в России между декабрём 2021 и декабрём 2024? "
            "Покажи разницу в п.п."
        ),
        "expected_tools": ["compare_periods"],
        "must_have": ["п.п", "п. п"],
        # must_have — OR-логика не реализована в базовом eval,
        # поэтому оставим must_have пустым, но comment объясняет
        "must_have": [],
        "comment": (
            "compare_periods(metric='cpi', period_a='2021-12', period_b='2024-12'). "
            "Агент должен вернуть delta (разницу в п.п.) между 8.39% и 9.52%."
        ),
    },

    # ── «Трудные» вопросы (Q7, Q8) ────────────────────────────────────────
    {
        "id": 7,
        "query": (
            "Какой был курс доллара в «начале февраля 2022»?"
        ),
        "expected_tools": ["get_fx_rate"],
        "must_have": [],
        "comment": (
            "ТРУДНЫЙ: неоднозначная дата «начало февраля 2022». Агент должен "
            "выбрать конкретную дату (1 или 2 февраля). Проблема — если модель "
            "возьмёт середину февраля, после 24.02 курс уже совсем другой (~76 vs 103). "
            "Реальный курс 1 февраля 2022 ≈ 76.7 руб/USD."
        ),
    },
    {
        "id": 8,
        "query": (
            "Индекс нищеты в марте 2022: сложи инфляцию г/г за март 2022 "
            "и безработицу за тот же месяц."
        ),
        "expected_tools": ["get_inflation", "get_unemployment", "calculate"],
        "must_have": ["%"],
        "comment": (
            "ТРУДНЫЙ: март 2022 — пиковая инфляция (16.69%) при рекордно низкой "
            "безработице (4.0%). Агент может перепутать порядок инструментов "
            "или взять безработицу за другой период. Ожидаемый результат ≈ 20.69%."
        ),
    },

    # ── Реальные макро-вопросы (Q9, Q10) ──────────────────────────────────
    {
        "id": 9,
        "query": (
            "Сколько евро можно купить за 1000 долларов по текущим курсам ЦБ? "
            "Считай через рублёвые курсы."
        ),
        "expected_tools": ["get_fx_rate", "calculate"],
        "must_have": ["евро"],
        "comment": (
            "Реальный вопрос: кросс-курс EUR/USD через рубль. "
            "Формула: 1000 * (USD/RUB) / (EUR/RUB). "
            "Актуально для путешественников и импортёров."
        ),
    },
    {
        "id": 10,
        "query": (
            "Сравни реальную ключевую ставку России в декабре 2021 "
            "(когда ставка ещё росла) и в апреле 2026. "
            "Где реальная ставка была выше?"
        ),
        "expected_tools": ["get_key_rate", "get_inflation", "calculate"],
        "must_have": ["%"],
        "comment": (
            "Реальный многошаговый вопрос: нужно получить 4 числа "
            "(2 ставки + 2 инфляции) и посчитать 2 реальные ставки. "
            "Дек 2021: номинал 8.5%, инфляция 8.39% → реальная ≈ 0.1%. "
            "Апр 2026: номинал 16%, инфляция ~5.98% → реальная ≈ 10%. "
            "Агент должен правильно сопоставить даты ставки и инфляции."
        ),
    },
]


def run_case(case: dict, *, use_cache: bool = False, track_cost: bool = False) -> dict:
    print(f"\n{'=' * 70}\n[Q{case['id']}] {case['query']}\n{'-' * 70}")

    res = run_agent(
        case["query"],
        max_iter=10,
        verbose=True,
        use_cache=use_cache,
        track_cost=track_cost,
    )

    used_tools = [e["call"] for e in res["trace"] if "call" in e]
    answer     = res.get("answer") or ""

    tool_match = all(t in used_tools for t in case["expected_tools"])
    text_match = all(s.lower() in answer.lower() for s in case["must_have"])
    ok = bool(answer) and tool_match and text_match

    print(f"\n  tools used : {used_tools}")
    print(f"  expected   : {case['expected_tools']} → {'OK' if tool_match else 'MISS'}")
    print(f"  answer     : {answer[:200]}")
    print(f"  must_have  : {case['must_have']} → {'OK' if text_match else 'MISS'}")
    print(f"  verdict    : {'PASS' if ok else 'FAIL'}")

    return {
        "id":         case["id"],
        "query":      case["query"],
        "ok":         ok,
        "tools_used": used_tools,
        "steps":      res["steps"],
        "answer":     answer,
    }


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Eval макро-агента (10 вопросов)")
    ap.add_argument("--cache", action="store_true",
                    help="Общий кэш инструментов на все вопросы")
    ap.add_argument("--cost",  action="store_true",
                    help="Показать токены и стоимость по шагам")
    ap.add_argument("--ids",   nargs="+", type=int, default=None,
                    help="Запустить только указанные ID вопросов (например --ids 5 6)")
    a = ap.parse_args()

    if a.cache:
        CACHE_STATS["hits"] = CACHE_STATS["misses"] = 0

    cases = CASES if not a.ids else [c for c in CASES if c["id"] in a.ids]
    results = [run_case(c, use_cache=a.cache, track_cost=a.cost) for c in cases]

    passed = sum(1 for r in results if r["ok"])
    print(f"\n{'=' * 70}")
    print(f"Итого: {passed}/{len(results)} пройдено\n")

    print(f"{'ID':>3} | {'ok?':>4} | {'шагов':>5} | {'инструменты'}")
    print("-" * 70)
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        tools_str = ", ".join(r["tools_used"]) or "—"
        print(f"{r['id']:>3} | {mark:>4} | {r['steps']:>5} | {tools_str}")

    if a.cache:
        h, m = CACHE_STATS["hits"], CACHE_STATS["misses"]
        print(
            f"\n[кэш] на {len(results)} вопросах: {h} попаданий из {h + m} "
            "обращений к инструментам."
        )

    out = Path(__file__).parent / "eval_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nРезультаты → {out}")


if __name__ == "__main__":
    main()
