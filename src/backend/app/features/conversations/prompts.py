from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts
from app.features.conversations.schemas import Message, PageContext, Quote

PROMPTS = load_prompts(prompts_py=__file__)


def chat_prompt(history: list[Message], page: PageContext | None = None) -> list[LLMMessage]:
    """The chat for Apertus; `page` is where in the e-banking the customer is right now."""
    # A truncated history can start with a reply; chat templates expect a user turn first.
    while history and history[0].role == "assistant":
        history = history[1:]
    system: LLMMessage = {"role": "system", "content": PROMPTS["chat_system"] + _page(page=page)}
    *earlier, last = history
    # ponytail: only the last turn sends its quotes, earlier ones live on in the replies
    turns: list[LLMMessage] = [{"role": m.role, "content": m.content} for m in earlier]
    return [system, *turns, {"role": last.role, "content": _text(message=last)}]


def _page(page: PageContext | None) -> str:
    if page is None:
        return ""
    if page.account_name is None:
        return PROMPTS["page"].format(title=page.title)
    return PROMPTS["page_account"].format(title=page.title, account=page.account_name)


def _text(message: Message) -> str:
    """The message's quotes, each with its comment, in front of its text."""
    return "".join(_quote(quote=quote) for quote in message.quotes) + message.content


def _quote(quote: Quote) -> str:
    # Escaped, a quote can neither close its block nor open a tag of its own.
    text = quote.text.replace("<", "&lt;").replace(">", "&gt;")
    block = PROMPTS["quote"].format(text=text)
    if quote.comment is None:
        return block
    return block + PROMPTS["quote_comment"].format(comment=quote.comment)
