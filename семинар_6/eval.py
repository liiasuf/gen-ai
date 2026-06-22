"""
Eval для Семинара 6: 6 вопросов × 3 конфигурации.

Конфигурации:
  S5  — одиночный агент из семинара 5 (agent_s5.run_agent)
  PWC — Планировщик-Исполнитель-Критик без валидатора схемы
  PWC+V — PWC с валидатором схемы (use_validator=True)

Запуск:
  python eval.py               # все вопросы, все конфиги
  python eval.py --ids 1 3     # только Q1 и Q3
  python eval.py --config pwc  # только PWC
  python eval.py --no-parallel # последовательный режим workers
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from agent_s5 import run_agent as run_s5
from orchestrator import run_pwc

# ── 6 вопросов ────────────────────────────────────────────────────────────
CASES = [
    {
        "id": 1,
        "query": "Какая сегодня ключевая ставка ЦБ РФ?",
        "expected_tools": ["get_key_rate"],
        "must_have": ["%"],
        "comment": "Простой запрос одного числа — базовый тест.",
    },
    {
        "id": 2,
        "query": "Сколько стоит доллар сегодня и сколько стоил 1 января 2022?",
        "expected_tools": ["get_fx_rate"],
        "must_have": [],
        "comment": "Два вызова get_fx_rate; у PWC — два подвопроса.",
    },
    {
        "id": 3,
        "query": "Какая сейчас реальная ключевая ставка? (номинальная минус инфляция г/г)",
        "expected_tools": ["get_key_rate", "get_inflation", "calculate"],
        "must_have": ["%"],
        "comment": "Три инструмента + арифметика. PWC должен выделить calculate в отдельный подвопрос.",
    },
    {
        "id": 4,
        "query": (
            "За сколько лет удвоится вклад при текущей ключевой ставке? "
            "Используй правило 72."
        ),
        "expected_tools": ["get_key_rate", "calculate"],
        "must_have": ["год"],
        "comment": "Формула 72 / ставка. Проверяем цепочку из двух подвопросов.",
    },
    {
        "id": 5,
        "query": "Во сколько раз вырос курс USD с января 2022 по апрель 2026?",
        "expected_tools": ["get_fx_rate", "calculate"],
        "must_have": ["раз"],
        "comment": "Сравнение двух дат: два get_fx_rate + calculate. Проверяем зависимости.",
    },
    {
        "id": 6,
        "query": (
            "Сравни реальную ключевую ставку России в декабре 2021 "
            "и в апреле 2026. Где она была выше и насколько?"
        ),
        "expected_tools": ["get_key_rate", "get_inflation", "calculate"],
        "must_have": ["%"],
        "comment": (
            "Сложный: 4 числа (2 ставки + 2 инфляции), 2 реальные ставки, "
            "затем сравнение. Проверяем параллельное исполнение независимых подвопросов."
        ),
    },
]

CONFIGS = ["s5", "pwc", "pwc+v"]


# ── Запуск одного вопроса в одной конфигурации ────────────────────────────

def run_case_s5(case: dict) -> dict:
    """Конфиг S5: одиночный агент из семинара 5."""
    t0 = time.perf_counter()
    res = run_s5(case["query"], max_iter=10, verbose=False)
    elapsed = round(time.perf_counter() - t0, 2)
    used_tools = [e["call"] for e in res.get("trace", []) if "call" in e]
    answer = res.get("answer") or ""
    tool_match = all(t in used_tools for t in case["expected_tools"])
    text_match = all(s.lower() in answer.lower() for s in case["must_have"])
    ok = bool(answer) and tool_match and text_match
    return {
        "config": "s5",
        "id": case["id"],
        "ok": ok,
        "tools_used": used_tools,
        "steps": res.get("steps", 0),
        "answer": answer[:300],
        "elapsed_sec": elapsed,
    }


def run_case_pwc(case: dict, *, use_validator: bool, parallel: bool = True) -> dict:
    """Конфиг PWC или PWC+V."""
    config_name = "pwc+v" if use_validator else "pwc"
    t0 = time.perf_counter()
    res = run_pwc(
        case["query"],
        max_iter=3,
        verbose=False,
        use_validator=use_validator,
        parallel=parallel,
    )
    elapsed = round(time.perf_counter() - t0, 2)
    answer = res.get("answer") or ""
    # Собираем все инструменты из worker-шагов
    used_tools: list[str] = []
    for step in res.get("trace", []):
        if step.get("kind") == "worker":
            used_tools.extend(step.get("used_tools", []))
    tool_match = all(t in used_tools for t in case["expected_tools"])
    text_match = all(s.lower() in answer.lower() for s in case["must_have"])
    ok = bool(answer) and tool_match and text_match
    return {
        "config": config_name,
        "id": case["id"],
        "ok": ok,
        "tools_used": list(dict.fromkeys(used_tools)),  # unique, order-preserving
        "iterations": res.get("iterations", 0),
        "answer": answer[:300],
        "elapsed_sec": elapsed,
        "plan_errors": res.get("trace", [{}])[0].get("plan_errors", []) if res.get("trace") else [],
    }


def main():
    ap = argparse.ArgumentParser(description="Eval С6: 6 вопросов × 3 конфига")
    ap.add_argument("--ids", nargs="+", type=int, default=None)
    ap.add_argument(
        "--config",
        choices=CONFIGS + ["all"],
        default="all",
        help="Какую конфигурацию запустить",
    )
    ap.add_argument("--no-parallel", action="store_true", help="Последовательный режим workers")
    a = ap.parse_args()

    cases = CASES if not a.ids else [c for c in CASES if c["id"] in a.ids]
    configs = CONFIGS if a.config == "all" else [a.config]
    parallel = not a.no_parallel

    all_results: list[dict] = []

    for case in cases:
        print(f"\n{'=' * 70}")
        print(f"[Q{case['id']}] {case['query']}")
        print(f"  ({case['comment']})")
        print("-" * 70)

        for config in configs:
            print(f"\n  --- config: {config.upper()} ---")
            try:
                if config == "s5":
                    r = run_case_s5(case)
                elif config == "pwc":
                    r = run_case_pwc(case, use_validator=False, parallel=parallel)
                else:  # pwc+v
                    r = run_case_pwc(case, use_validator=True, parallel=parallel)
            except Exception as e:
                r = {
                    "config": config,
                    "id": case["id"],
                    "ok": False,
                    "tools_used": [],
                    "answer": f"(exception: {e})",
                    "elapsed_sec": 0,
                }

            mark = "PASS" if r["ok"] else "FAIL"
            print(f"  verdict    : {mark}")
            print(f"  tools      : {r['tools_used']}")
            print(f"  answer     : {r['answer'][:200]}")
            elapsed = r.get("elapsed_sec", "?")
            print(f"  elapsed    : {elapsed}s")
            all_results.append(r)

    # ── Итоговая таблица ──────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"{'ID':>3} | {'config':>6} | {'ok?':>4} | {'ответ (начало)'}")
    print("-" * 70)
    for r in all_results:
        mark = "PASS" if r["ok"] else "FAIL"
        snippet = r["answer"][:60].replace("\n", " ")
        print(f"{r['id']:>3} | {r['config']:>6} | {mark:>4} | {snippet}")

    # Сводка по конфигам
    print(f"\n{'=' * 70}")
    for config in configs:
        sub = [r for r in all_results if r["config"] == config]
        passed = sum(1 for r in sub if r["ok"])
        print(f"  {config.upper():6}: {passed}/{len(sub)} passed")

    # Сохранить JSON
    out = Path(__file__).parent / "eval6_results.json"
    out.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nРезультаты → {out}")


if __name__ == "__main__":
    main()
