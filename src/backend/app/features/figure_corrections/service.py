from app.clients.apertus import ApertusClient, LLMResult, Model
from app.core.errors import UpstreamError
from app.features.figure_corrections.prompts import correction_prompt

CORRECTION_MODEL = Model.SMART
CORRECTION_PURPOSE = "figure_correction"
# How much of the sources the correction sees; the first sources drop out first.
SOURCES_MAX_CHARS = 24000


class FigureCorrectionService:
    def __init__(self, apertus: ApertusClient) -> None:
        self.apertus = apertus

    async def correct_figures(
        self, answer: str, missing: list[str], sources: list[str]
    ) -> LLMResult[str]:
        """The answer rewritten by Apertus without the figures that no source holds."""
        # Streamed, so the timeout counts the wait per chunk, not the whole answer.
        stream = self.apertus.stream_chat(
            messages=correction_prompt(
                answer=answer,
                missing=missing,
                data="\n".join(last_sources(sources=sources, max_chars=SOURCES_MAX_CHARS)),
            ),
            model=CORRECTION_MODEL,
            purpose=CORRECTION_PURPOSE,
        )
        async for _ in stream:
            pass
        if stream.result is None:
            raise UpstreamError("Apertus stream ended without a result")
        return stream.result


# Whole sources only: a cut inside a tool result would leave broken JSON.
def last_sources(sources: list[str], max_chars: int) -> list[str]:
    kept: list[str] = []
    total = 0
    for source in reversed(sources):
        if total + len(source) > max_chars:
            break
        kept.append(source)
        total += len(source)
    return kept[::-1]
