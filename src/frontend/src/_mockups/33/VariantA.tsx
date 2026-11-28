import { Chat, FlagList, Header, Tiles } from "./shared";

/** A: a "Needs attention" box above the board, shown every time the TrustRoom opens. */
export function VariantA() {
  return (
    <div className="m-page">
      <Header />
      <div className="m-body">
        <main className="m-board">
          <section className="f-box">
            <h2>Needs attention</h2>
            <FlagList />
          </section>
          <Tiles />
        </main>
        <Chat />
      </div>
    </div>
  );
}
