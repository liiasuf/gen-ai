from __future__ import annotations

import argparse
import random
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt
import pandas as pd

from llm_client import get_model, make_client
from prompts import SYSTEM_PROMPT, user_prompt
from schema import CITIES, Application

N = 50
PER_CITY = N // len(CITIES)
WORKERS = 6

SPECIALITIES = [
    "учитель начальных классов",
    "воспитатель",
    "медсестра",
    "бухгалтер",
    "юрист",
    "инженер-конструктор",
    "логист",
    "HR-специалист",
    "социальный работник",
]

_thread_local = threading.local()
_reject_lock = threading.Lock()


def get_client():
    if not hasattr(_thread_local, "client"):
        _thread_local.client = make_client()
    return _thread_local.client


def seeds(count: int = N) -> list[tuple[str, str | None]]:
    per = max(1, count // len(CITIES))
    out: list[tuple[str, str | None]] = []
    for i, city in enumerate(CITIES):
        for j in range(per):
            out.append((city, SPECIALITIES[(i * per + j) % len(SPECIALITIES)]))
    random.shuffle(out)
    return out[:count]


def generate_one(model: str, city: str, speciality: str | None, rejects: Counter) -> Application:
    app = get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(city, speciality)},
        ],
        response_model=Application,
        max_retries=3,
        temperature=0.8,
    )
    if app.address.city != city:
        raise ValueError(f"ожидался {city}, получен {app.address.city}")
    return app


def to_df(apps: list[Application]) -> pd.DataFrame:
    rows = []
    for a in apps:
        r = a.model_dump()
        r["city"] = a.address.city
        r["district"] = a.address.district
        del r["address"]
        rows.append(r)
    return pd.DataFrame(rows)


def plots(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    df["city"].value_counts().sort_index().plot(kind="bar", ax=ax)
    ax.set_title("Города")
    ax.set_ylabel("заявок")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig("cities.png", dpi=120)
    plt.close()

    fig, ax = plt.subplots(figsize=(9, 5))
    df["speciality"].value_counts().plot(kind="bar", ax=ax)
    ax.set_title("Специальности")
    ax.set_ylabel("заявок")
    plt.xticks(rotation=35, ha="right")
    plt.tight_layout()
    fig.savefig("specialities.png", dpi=120)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=N)
    parser.add_argument("-w", type=int, default=WORKERS)
    args = parser.parse_args()

    random.seed(42)
    model = get_model()
    plan = seeds(args.n)
    rejects: Counter = Counter()
    failed = 0
    done: dict[int, Application] = {}

    print(f"модель {model}, заявок {len(plan)}, потоков {args.w}\n")

    def job(item: tuple[int, str, str | None]):
        idx, city, spec = item
        try:
            return idx, generate_one(model, city, spec, rejects), None
        except Exception as e:
            err = str(e).lower()
            if "graduation" in err or "окончания" in err or "возраст" in err:
                with _reject_lock:
                    rejects["age_year"] += 1
            return idx, None, e

    items = [(i + 1, c, s) for i, (c, s) in enumerate(plan)]
    with ThreadPoolExecutor(max_workers=args.w) as pool:
        for fut in as_completed(pool.submit(job, it) for it in items):
            idx, app, err = fut.result()
            if app:
                done[idx] = app
                print(f"{idx}/{len(plan)} {app.full_name}, {app.address.city}")
            else:
                failed += 1
                print(f"{idx}/{len(plan)} ошибка: {err}")

    apps = [done[i] for i in sorted(done)]
    print(f"\nготово: {len(apps)}/{len(plan)}, сбоев: {failed}")
    if rejects:
        print("валидатор:", dict(rejects))

    df = to_df(apps)
    df.to_csv("applications.csv", index=False, encoding="utf-8")
    plots(df)
    print("applications.csv, cities.png, specialities.png")


if __name__ == "__main__":
    main()
