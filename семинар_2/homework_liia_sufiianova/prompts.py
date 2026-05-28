import random

SYSTEM_PROMPT = """Ты заполняешь анкету на курс повышения квалификации (ДПО).
Нужна одна правдоподобная заявка: ФИО, возраст, адрес, текущая специальность,
желаемый курс, стаж, год окончания вуза. Ответ — JSON по схеме.

Город в address.city должен совпадать с городом из сообщения пользователя.
speciality и desired_course — только из допустимых значений схемы.
Согласуй возраст, год окончания и стаж."""

USER_PROMPT = "Создай одну заявку на курс ДПО."


def user_prompt(city: str, speciality: str | None) -> str:
    spec = f"Текущая специальность: {speciality}." if speciality else ""
    return (
        f"{USER_PROMPT} Город проживания: {city}. {spec} "
        f"Заявка №{random.randint(100, 999)}."
    )
