from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CITIES = (
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Самара",
    "Краснодар",
    "Воронеж",
    "Ростов-на-Дону",
)

SPECIALITIES = Literal[
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

DESIRED_COURSES = Literal[
    "цифровые инструменты педагога",
    "управление персоналом",
    "налогообложение и отчётность",
    "медицинская реабилитация",
    "проектирование в CAD",
    "основы Data Science для гуманитариев",
    "деловое общение и переговоры",
]

City = Literal[
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Самара",
    "Краснодар",
    "Воронеж",
    "Ростов-на-Дону",
]


class Address(BaseModel):
    city: City
    district: str = Field(min_length=2, max_length=40)


class Application(BaseModel):
    full_name: str = Field(min_length=5, max_length=80)
    age: int = Field(ge=22, le=65)
    address: Address
    speciality: SPECIALITIES
    desired_course: DESIRED_COURSES
    years_of_experience: int = Field(ge=0, le=40)
    graduation_year: int = Field(ge=1980, le=2024)

    @field_validator("graduation_year")
    @classmethod
    def graduation_year_in_range(cls, v: int) -> int:
        current_year = date.today().year
        if v < 1970 or v > current_year:
            raise ValueError(
                f"Год окончания вуза должен быть между 1970 и {current_year}"
            )
        return v

    @model_validator(mode="after")
    def age_matches_graduation(self) -> "Application":
        current_year = date.today().year
        birth_year = current_year - self.age
        min_graduation = birth_year + 22
        if self.graduation_year < min_graduation:
            raise ValueError(
                f"При возрасте {self.age} год окончания не может быть раньше {min_graduation}"
            )
        if self.graduation_year > current_year:
            raise ValueError("Год окончания не может быть в будущем")
        return self
