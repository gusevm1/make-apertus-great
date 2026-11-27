from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.core.prompts import load_prompts
from app.core.provenance import Provenance

PROMPTS = load_prompts(prompts_py=__file__)


class GuardrailCategory(StrEnum):
    PRODUCT_CHOICE = "product_choice"
    FORECAST = "forecast"
    TAX_ADVICE = "tax_advice"
    NEW_CREDIT = "new_credit"
    OTHER_CUSTOMER = "other_customer"
    OFF_TOPIC = "off_topic"
    OK = "ok"


class GuardrailCheck(BaseModel):
    category: GuardrailCategory = Field(description=PROMPTS["category"])
    language: Literal["de", "en"] = Field(description=PROMPTS["language"])

    @model_validator(mode="before")
    @classmethod
    def unwrap(cls, data: Any) -> Any:
        # The small model nests its answer under the schema's name.
        if isinstance(data, dict) and set(data) == {cls.__name__}:
            return data[cls.__name__]
        return data


class Advisor(BaseModel):
    advisor_name: str | None = None
    advisor_phone: str | None = None


class Guardrail(BaseModel):
    category: GuardrailCategory
    # Replaces the answer: no tool and no answer call runs.
    decline: str | None
    # Follows the answer, written by the server, never by the model.
    pointer: str | None
    provenance: Provenance
