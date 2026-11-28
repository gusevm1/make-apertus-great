import { Chat, FlagList, Header, Tiles } from "./shared";

/** C: the flags open the chat column, above the conversation, until dismissed. */
export function VariantC() {
  return (
    <div className="m-page">
      <Header />
      <div className="m-body">
        <main className="m-board">
          <Tiles />
        </main>
        <Chat
          top={
            <section className="c-card">
              <h2>Since your last visit</h2>
              <FlagList />
            </section>
          }
        />
      </div>
    </div>
  );
}
