import { useState } from "react";
import type { Conversation } from "./api";
import type { HostContext } from "./host";
import { Icon, type IconName } from "./Icon";

// Only what the tools can answer today; the web row holds when SEARXNG_URL is set.
const CAPABILITIES: { icon: IconName; title: string; detail: string }[] = [
  {
    icon: "accounts",
    title: "Balances, income and spending",
    detail: "Your accounts, cards and portfolio, added up from your bookings",
  },
  {
    icon: "payments",
    title: "Payments and standing orders",
    detail: "What went out, what is due, who you pay",
  },
  {
    icon: "file",
    title: "Your documents",
    detail: "Attach a PDF or photo and ask about it",
  },
  {
    icon: "search",
    title: "The web, only when you allow it",
    detail: "You see each search query before it leaves the bank",
  },
];

interface Props {
  context: HostContext;
  chats: ChatListProps;
  isBusy: boolean;
  onAsk: (question: string) => void;
}

/** The empty chat: questions for the page the customer is on, past chats, and what can be asked. */
export function Home({ context, chats, isBusy, onAsk }: Props) {
  const account = context.account;
  return (
    <section className="home">
      <p className="ai-notice">
        You are talking to an AI. It works with your own data only and gives no
        investment advice.
      </p>
      <p className="hint">
        Ask about your accounts, cards and documents. Every figure comes from
        your bank data.
      </p>
      <div className="card">
        <div className="card-head">
          <h2>
            {account === null
              ? "Ask about your money"
              : `Ask about ${account.name}`}
          </h2>
          {account !== null && <span className="hint">{account.iban}</span>}
        </div>
        <ul className="rows">
          {suggestionsFor(account?.name ?? null).map((question) => (
            <li key={question}>
              <button
                type="button"
                className="row"
                onClick={() => onAsk(question)}
                disabled={isBusy}
              >
                <span className="row-main">{question}</span>
                <Icon name="chevronRight" size={16} />
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="home-chats">
        <ChatList {...chats} />
      </div>
      <div className="card">
        <h2>What TrustRoom can answer</h2>
        <ul className="capabilities">
          {CAPABILITIES.map((capability) => (
            <li key={capability.title}>
              <span className="capability-icon">
                <Icon name={capability.icon} />
              </span>
              <span>
                <strong>{capability.title}</strong>
                <small>{capability.detail}</small>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function suggestionsFor(accountName: string | null): string[] {
  if (accountName === null) {
    return [
      "How much money do I have?",
      "Which payments are due in the next weeks?",
      "Where did most of my money go last month?",
    ];
  }
  return [
    `What came in and went out of ${accountName} this month?`,
    `Which standing orders go out of ${accountName}?`,
    "Where did most of my money go last month?",
  ];
}

export interface ChatListProps {
  conversations: Conversation[];
  currentId: string | null;
  isLoading: boolean;
  isBusy: boolean;
  onOpen: (id: string) => void;
}

/** The customer's past chats, newest first, as rows like the e-banking's account list. */
export function ChatList({
  conversations,
  currentId,
  isLoading,
  isBusy,
  onOpen,
}: ChatListProps) {
  const [isShowingAll, setIsShowingAll] = useState(false);
  const shown = isShowingAll
    ? conversations
    : conversations.slice(0, CHATS_SHOWN);
  return (
    <nav className="card" aria-label="Past chats">
      <div className="card-head">
        <h2>Recent chats</h2>
        {conversations.length > CHATS_SHOWN && (
          <button
            type="button"
            className="link"
            onClick={() => setIsShowingAll(!isShowingAll)}
          >
            {isShowingAll ? "Show fewer" : "Show all"}
          </button>
        )}
      </div>
      {isLoading && <p className="hint">Loading your chats…</p>}
      {!isLoading && conversations.length === 0 && (
        <p className="hint">No chats yet.</p>
      )}
      <ul className="rows">
        {shown.map((conversation) => (
          <li key={conversation.id}>
            <button
              type="button"
              className="row"
              onClick={() => onOpen(conversation.id)}
              disabled={isBusy}
              aria-current={conversation.id === currentId ? "page" : undefined}
            >
              <span className="row-main single">
                {conversation.title ?? "Untitled chat"}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const CHATS_SHOWN = 5;
