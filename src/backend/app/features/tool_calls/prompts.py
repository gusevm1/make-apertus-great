import json
import re
from datetime import date, timedelta
from typing import Any

from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts
from app.core.tools import Tool
from app.features.tool_calls.schemas import ToolCall, ToolDecision

PROMPTS = load_prompts(prompts_py=__file__)
TOOL_RESULT_MAX_CHARS = 6000
# The blocks `chat_prompt` puts in front of the question; their own text is escaped.
BLOCK_END = re.compile(r"</(?:customer|document|page|quote)>")
# ponytail: common words of four languages, ask the model once other languages matter
COMMON_WORDS = {
    language: set(words.split())
    for language, words in {
        "English": "and are at did do does for how is much my of show that the this to"
        " what when where which who why with you your",
        "German": "auf bei bin das dem den der ein eine für habe hat ich im ist mein"
        " meine meinem meinen mir mit sind und viel von wie wo zeig zu",
        "French": "ai au avec combien dans est et je les ma mes mon où pour quel quelle"
        " quels qui sur une vous à",
        "Italian": "che cosa di gli ho mia miei mio nel per quale quali sono è",
    }.items()
}


type ToolRound = tuple[ToolDecision, list[ToolCall]]


def decision_prompt(
    messages: list[LLMMessage], rounds: list[ToolRound], tools: list[Tool[Any]], today: date
) -> list[LLMMessage]:
    tool_lines = "\n".join(_tool_line(tool=tool) for tool in tools)
    system: LLMMessage = {
        "role": "system",
        "content": PROMPTS["decision_system"].format(today=_today(today=today), tools=tool_lines),
    }
    prompt = [system, *(message for message in messages if message["role"] != "system")]
    for decision, calls in rounds:
        prompt.append({"role": "assistant", "content": decision.model_dump_json()})
        prompt.append({"role": "user", "content": _decision_feedback(calls=calls)})
    return prompt


def answer_prompt(messages: list[LLMMessage], calls: list[ToolCall]) -> list[LLMMessage]:
    # Named outright, because German results or an image otherwise pull the answer elsewhere.
    language = question_language(message=messages[-1])
    language_line = (
        PROMPTS["answer_language_unknown"]
        if language is None
        else PROMPTS["answer_language"].format(language=language)
    )
    if not calls:
        content = PROMPTS["answer_direct"].format(language=language_line)
        return [*messages, {"role": "user", "content": content}]
    results = "".join(_tool_result(call=call) for call in calls)
    content = PROMPTS["answer_results"].format(results=results, language=language_line)
    if any(call.tool_name == "build_widget" and call.error is None for call in calls):
        content += PROMPTS["answer_widget"]
    return [*messages, {"role": "user", "content": content}]


def question_language(message: LLMMessage) -> str | None:
    content = message["content"]
    if not isinstance(content, str):
        content = " ".join(part["text"] for part in content if part["type"] == "text")
    # The English wording of a document, page or quote block would outvote a short German question.
    content = BLOCK_END.split(content)[-1]
    words = re.findall(r"[^\W\d_]+", content.lower())
    ranked = sorted(
        (
            (sum(word in common for word in words), language)
            for language, common in COMMON_WORDS.items()
        ),
        reverse=True,
    )
    (top_count, language), (second_count, _) = ranked[:2]
    return language if top_count > second_count else None


def dated_prompt(messages: list[LLMMessage], today: date) -> list[LLMMessage]:
    system, *turns = messages
    return [{"role": "system", "content": f"{system['content']}\n{_today(today=today)}"}, *turns]


def _today(today: date) -> str:
    # The model gets "last month" wrong, so the server works the periods out.
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    return PROMPTS["today"].format(
        weekday=f"{today:%A}",
        date=f"{today:%d.%m.%Y}",
        today=today,
        month_start=month_start,
        last_month_start=last_month_end.replace(day=1),
        last_month_end=last_month_end,
        year_start=date(today.year, 1, 1),
        last_year_start=date(today.year - 1, 1, 1),
        last_year_end=date(today.year - 1, 12, 31),
    )


def _tool_line(tool: Tool[Any]) -> str:
    arguments = json.dumps(tool.args_schema.model_json_schema())
    return PROMPTS["decision_tool"].format(
        name=tool.name, description=tool.description, arguments=arguments
    )


def _decision_feedback(calls: list[ToolCall]) -> str:
    has_failed = any(call.error is not None for call in calls)
    next_step = PROMPTS["decision_retry"] if has_failed else PROMPTS["decision_next"]
    return "".join(_tool_result(call=call) for call in calls) + next_step


def _tool_result(call: ToolCall) -> str:
    tool = _data(text=json.dumps(call.tool_name, ensure_ascii=False))
    reason = _data(text=call.reason)
    if call.error is not None:
        error = _cut(text=_data(text=call.error))
        return PROMPTS["tool_error"].format(tool=tool, reason=reason, error=error)
    result = _cut(text=_data(text=json.dumps(call.result, ensure_ascii=False)))
    return PROMPTS["tool_result"].format(tool=tool, reason=reason, result=result)


def _cut(text: str) -> str:
    if len(text) <= TOOL_RESULT_MAX_CHARS:
        return text
    return text[:TOOL_RESULT_MAX_CHARS] + PROMPTS["tool_result_cut"]


def _data(text: str) -> str:
    # Written as JSON escapes, a result can neither close its block nor open a tag of its own.
    return text.replace("<", "\\u003c").replace(">", "\\u003e")
