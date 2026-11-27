import logging
import time

from app.clients.apertus import ApertusClient, Model
from app.core.errors import UpstreamError
from app.core.provenance import Check, Provenance
from app.features.guardrails.prompts import (
    advisor_pointer,
    check_prompt,
    counselling_pointer,
    decline,
)
from app.features.guardrails.schemas import (
    CustomerAdvisor,
    Guardrail,
    GuardrailCategory,
    GuardrailCheck,
)
from app.features.ledger.service import LedgerService

CHECK_MODEL = Model.FAST
CHECK_PURPOSE = "guardrail_check"
CHECK_NAME = "guardrail"
ADVISOR_CATEGORIES = {
    GuardrailCategory.PRODUCT_CHOICE,
    GuardrailCategory.FORECAST,
    GuardrailCategory.TAX_ADVICE,
}

logger = logging.getLogger(__name__)


class GuardrailService:
    def __init__(self, apertus: ApertusClient, ledger: LedgerService, token: str) -> None:
        self.apertus = apertus
        self.ledger = ledger
        self.token = token

    async def check_message(self, text: str) -> Guardrail:
        """Sort the message; a decline replaces the answer, a pointer follows it."""
        started = time.perf_counter()
        try:
            result = await self.apertus.structured(
                messages=check_prompt(text=text),
                schema=GuardrailCheck,
                model=CHECK_MODEL,
                purpose=CHECK_PURPOSE,
            )
        except UpstreamError:
            # Without the check the turn answers as it would have before guardrails existed.
            logger.exception("Guardrail check failed")
            return Guardrail(
                category=GuardrailCategory.OK,
                decline=None,
                pointer=None,
                provenance=Provenance(
                    model=CHECK_MODEL.value,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    checks=[Check(name=CHECK_NAME, passed=False, detail="check failed")],
                ),
            )
        check = result.content
        return Guardrail(
            category=check.category,
            decline=self._decline(check=check),
            pointer=await self._pointer(check=check),
            provenance=Provenance(
                model=result.model,
                latency_ms=result.latency_ms,
                checks=[Check(name=CHECK_NAME, passed=True, detail=check.category.value)],
            ),
        )

    def _decline(self, check: GuardrailCheck) -> str | None:
        if check.category == GuardrailCategory.OFF_TOPIC:
            return decline(category="off_topic", language=check.language)
        if check.category == GuardrailCategory.OTHER_CUSTOMER:
            return decline(category="other_customer", language=check.language)
        return None

    async def _pointer(self, check: GuardrailCheck) -> str | None:
        if check.category == GuardrailCategory.NEW_CREDIT:
            return counselling_pointer(language=check.language)
        if check.category not in ADVISOR_CATEGORIES:
            return None
        customer = await self.ledger.read(path="/customer", token=self.token)
        advisor = CustomerAdvisor.model_validate(customer).advisor
        return advisor_pointer(advisor=advisor, language=check.language)
