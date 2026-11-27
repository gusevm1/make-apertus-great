from collections.abc import Sequence

from app.clients.apertus import Message as LLMMessage
from app.core.prompts import load_prompts
from app.features.conversations.schemas import Message, PageContext, Quote
from app.features.documents.schemas import Document

PROMPTS = load_prompts(prompts_py=__file__)
# ponytail: a long contract is cut here; search inside documents once they outgrow the prompt
DOCUMENT_MAX_CHARS = 20_000


def chat_prompt(
    history: list[Message],
    page: PageContext | None = None,
    documents: Sequence[Document] = (),
) -> list[LLMMessage]:
    """The chat for Apertus; `page` and `documents` go with the last message."""
    # A truncated history can start with a reply; chat templates expect a user turn first.
    while history and history[0].role == "assistant":
        history = history[1:]
    system: LLMMessage = {"role": "system", "content": PROMPTS["chat_system"]}
    *earlier, last = history
    # ponytail: only the last turn sends its quotes and documents; earlier ones live on in replies
    turns: list[LLMMessage] = [{"role": m.role, "content": m.content} for m in earlier]
    # The page goes with the question, not into the system message: the tool decision only
    # sees the turns, and what the browser sends has no place in the system role.
    # Only what the customer sent with this message; everything else the model reads by a tool.
    blocks = "".join(_document(document=document) for document in documents)
    blocks += _page(page=page)
    return [system, *turns, {"role": last.role, "content": blocks + _text(message=last)}]


def _page(page: PageContext | None) -> str:
    if page is None:
        return ""
    if page.account_name is None:
        return PROMPTS["page"].format(title=_escaped(text=page.title))
    return PROMPTS["page_account"].format(
        title=_escaped(text=page.title), account=_escaped(text=page.account_name)
    )


def _escaped(text: str) -> str:
    # Escaped, a text can neither close its block nor open a tag of its own.
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _document(document: Document) -> str:
    # Escaped, a document can neither close its block nor open a tag of its own.
    text = document.markdown[:DOCUMENT_MAX_CHARS].replace("<", "&lt;").replace(">", "&gt;")
    if len(document.markdown) > DOCUMENT_MAX_CHARS:
        text += PROMPTS["document_cut"]
    # The name comes from the upload: on one line, and unable to end the attribute or the tag.
    name = _escaped(text=" ".join(document.name.split())).replace('"', "'")
    return PROMPTS["document"].format(name=name, text=text)


def _text(message: Message) -> str:
    """The message's quotes, each with its comment, in front of its text."""
    return "".join(_quote(quote=quote) for quote in message.quotes) + message.content


def _quote(quote: Quote) -> str:
    block = PROMPTS["quote"].format(text=_escaped(text=quote.text))
    if quote.comment is None:
        return block
    return block + PROMPTS["quote_comment"].format(comment=quote.comment)
