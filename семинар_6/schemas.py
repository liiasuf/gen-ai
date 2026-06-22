"""
JSON-схемы инструментов для OpenAI-совместимого API вызова инструментов.
Семинар 5: добавлена схема для compare_periods (инструмент 6).
"""

TOOL_SCHEMAS = [
    # ----- 1. Калькулятор -----
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Безопасный математический калькулятор. Понимает +, -, *, /, ^, "
                "sqrt, ln, log, exp, скобки. Использовать для любых вычислений "
                "над числами, полученными от других инструментов — руками не считать."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "Математическое выражение, например '(21 - 9.5)' или "
                            "'log(2) / log(1 + 0.17)'."
                        ),
                    },
                },
                "required": ["expression"],
            },
        },
    },
    # ----- 2. Курс валюты -----
    {
        "type": "function",
        "function": {
            "name": "get_fx_rate",
            "description": (
                "Официальный курс валюты к рублю на дату по данным ЦБ РФ. "
                "Зови, если вопрос про курс USD/EUR/CNY/прочих — не придумывай курс."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "description": "ISO-код валюты: USD, EUR, CNY, GBP, JPY, TRY и т.д.",
                    },
                    "on_date": {
                        "type": ["string", "null"],
                        "description": "Дата YYYY-MM-DD. Если не задана — сегодня.",
                    },
                },
                "required": ["currency"],
            },
        },
    },
    # ----- 3. Ключевая ставка -----
    {
        "type": "function",
        "function": {
            "name": "get_key_rate",
            "description": (
                "Ключевая ставка Банка России на дату, % годовых. Для текущей — "
                "с cbr.ru, для исторической — из локального архива изменений ставки."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "on_date": {
                        "type": ["string", "null"],
                        "description": "Дата YYYY-MM-DD. Если не задана — сегодня.",
                    },
                },
            },
        },
    },
    # ----- 4. Инфляция (ИПЦ) -----
    {
        "type": "function",
        "function": {
            "name": "get_inflation",
            "description": (
                "Индекс потребительских цен Росстата, % г/г, на конец месяца. "
                "Для инфляции и реальной доходности."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":  {"type": "integer", "description": "Год, например 2024"},
                    "month": {
                        "type": "integer",
                        "description": "Месяц 1..12 (1 = январь)",
                        "minimum": 1,
                        "maximum": 12,
                    },
                },
                "required": ["year", "month"],
            },
        },
    },
    # ----- 5. Безработица -----
    {
        "type": "function",
        "function": {
            "name": "get_unemployment",
            "description": (
                "Уровень безработицы (МОТ) Росстата, % от рабочей силы, на конец "
                "месяца. Для «индекса нищеты» (инфляция + безработица)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year":  {"type": "integer", "description": "Год, например 2024"},
                    "month": {
                        "type": "integer",
                        "description": "Месяц 1..12 (1 = январь)",
                        "minimum": 1,
                        "maximum": 12,
                    },
                },
                "required": ["year", "month"],
            },
        },
    },
    # ----- 6. Сравнение двух периодов (домашнее задание) -----
    {
        "type": "function",
        "function": {
            "name": "compare_periods",
            "description": (
                "Сравнить значение одной макроэкономической метрики в двух разных "
                "периодах. Возвращает значения в обоих периодах, абсолютную разницу "
                "(delta = b - a) и отношение (ratio = b / a). "
                "Используй, когда нужно ответить «насколько выросло/упало», "
                "«во сколько раз изменилось» или сравнить два момента времени."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": [
                            "key_rate",
                            "fx_USD",
                            "fx_EUR",
                            "fx_CNY",
                            "cpi",
                            "unemployment",
                        ],
                        "description": (
                            "Метрика для сравнения: "
                            "key_rate — ключевая ставка ЦБ; "
                            "fx_USD/fx_EUR/fx_CNY — курс доллара/евро/юаня к рублю; "
                            "cpi — инфляция г/г по Росстату; "
                            "unemployment — безработица по Росстату."
                        ),
                    },
                    "period_a": {
                        "type": "string",
                        "description": (
                            "Первый (более ранний) период. "
                            "Формат: YYYY-MM-DD или YYYY-MM (будет взят первый день месяца)."
                        ),
                    },
                    "period_b": {
                        "type": "string",
                        "description": (
                            "Второй (более поздний) период. "
                            "Формат: YYYY-MM-DD или YYYY-MM."
                        ),
                    },
                },
                "required": ["metric", "period_a", "period_b"],
            },
        },
    },
]
