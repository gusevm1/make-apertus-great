from app.core.prompts import load_prompts

PROMPTS = load_prompts(prompts_py=__file__)


def transcription_instruction() -> str:
    return PROMPTS["transcribe"]
