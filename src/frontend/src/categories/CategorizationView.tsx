import { useEffect, useState } from "react";
import { api, json, requestErrorOf } from "../api";
import "./categories.css";
import {
  type CategorisationRun,
  createCategory,
  createTag,
  decide,
  type Decision,
  decisionsOf,
  judgeAgain,
  labelOf,
  latestRun,
  loadAll,
  type Loaded,
  setNecessity,
  stepText,
} from "./data";
import { DecisionList, SwipeDeck } from "./Decisions";
import { Overview } from "./Overview";

// A run works in the background for minutes, so the page asks for it again this often.
const RUN_POLL_MS = 3000;
const LAYOUT_KEY = "trustroom.categorization.layout";

type Layout = "list" | "swipe";

function storedLayout(): Layout {
  try {
    return localStorage.getItem(LAYOUT_KEY) === "swipe" ? "swipe" : "list";
  } catch {
    return "list";
  }
}

function isGoing(run: CategorisationRun | null): boolean {
  return run !== null && (run.status === "queued" || run.status === "running");
}

/** The Categorization view: settle what Apertus was unsure of, and see what each category holds. */
export function CategorizationView({
  token,
  onBack,
}: {
  token: string;
  onBack: () => void;
}) {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [run, setRun] = useState<CategorisationRun | null>(null);
  const [view, setView] = useState<"decide" | "overview">("decide");
  const [layout, setLayout] = useState<Layout>(storedLayout);
  const [busyId, setBusyId] = useState<string | null>(null);
  // Counts failed looks at the run, so a failed one schedules the next.
  const [pollFailures, setPollFailures] = useState(0);
  // Decided in this visit: hidden at once, before the reload shows them settled.
  const [decided, setDecided] = useState<Set<string>>(new Set());

  async function reload() {
    setLoaded(await loadAll(token));
  }

  useEffect(() => {
    let isCurrent = true;
    async function load() {
      try {
        // Starts a run for bookings still without a category, or returns the one going.
        const [next, current] = await Promise.all([
          loadAll(token),
          api<CategorisationRun>("/api/categorisations", token, json({})),
        ]);
        if (!isCurrent) return;
        setLoaded(next);
        setRun(current);
      } catch (failure) {
        if (isCurrent) setLoadError(requestErrorOf(failure).message);
      }
    }
    void load();
    return () => {
      isCurrent = false;
    };
  }, [token]);

  // While a run goes, ask for it again; when it ends, show what it decided.
  const runId = run?.id ?? null;
  const runGoing = isGoing(run);
  useEffect(() => {
    if (runId === null || !runGoing) return;
    let isCurrent = true;
    const timer = window.setTimeout(async () => {
      try {
        const next = await api<CategorisationRun>(
          `/api/categorisations/${runId}`,
          token,
        );
        if (!isCurrent) return;
        if (isGoing(next)) {
          setRun({ ...next });
          return;
        }
        // A request to judge again during the run starts a follow-up under a new id.
        const newest = await latestRun(token);
        if (!isCurrent) return;
        await reload();
        setRun(newest);
        setNotice(null);
      } catch {
        // Asks again after the same wait; the decisions shown stay usable.
        if (isCurrent) setPollFailures((count) => count + 1);
      }
    }, RUN_POLL_MS);
    return () => {
      isCurrent = false;
      window.clearTimeout(timer);
    };
  }, [runId, runGoing, run, pollFailures, token]);

  function chooseLayout(next: Layout) {
    setLayout(next);
    try {
      localStorage.setItem(LAYOUT_KEY, next);
    } catch {
      // The choice then lasts only for this visit.
    }
  }

  async function startAgain(message: string) {
    setRun(await judgeAgain(token));
    setNotice(message);
  }

  async function choose(decision: Decision, category: string) {
    setBusyId(decision.id);
    setError(null);
    setDecided((current) => new Set(current).add(decision.id));
    try {
      await decide(token, decision, category);
    } catch (failure) {
      setDecided((current) => {
        const next = new Set(current);
        next.delete(decision.id);
        return next;
      });
      setError(
        `${decision.payee} was not saved. ${requestErrorOf(failure).message}`,
      );
      setBusyId(null);
      return;
    }
    // The next card can be decided while the settled rows load.
    setBusyId(null);
    try {
      await reload();
    } catch {
      // Saved; the list shows it settled on the next load.
    }
  }

  async function createAndChoose(
    decision: Decision,
    name: string,
    description: string,
  ) {
    setBusyId(decision.id);
    setError(null);
    try {
      await createCategory(token, name, description);
    } catch (failure) {
      setError(`“${name}” was not added. ${requestErrorOf(failure).message}`);
      setBusyId(null);
      return;
    }
    // The category exists from here on; what fails later is said as such.
    await choose(decision, name);
    try {
      await startAgain(
        `Apertus is sorting your other bookings again, now with “${name}”.`,
      );
    } catch (failure) {
      setError(
        `“${name}” was added, but Apertus did not start sorting again. ${requestErrorOf(failure).message}`,
      );
    }
  }

  async function add(
    kind: "category" | "tag",
    name: string,
    description: string,
  ): Promise<boolean> {
    setBusyId(kind);
    setError(null);
    try {
      if (kind === "category") await createCategory(token, name, description);
      else await createTag(token, name, description);
    } catch (failure) {
      setError(`“${name}” was not added. ${requestErrorOf(failure).message}`);
      setBusyId(null);
      return false;
    }
    try {
      await reload();
      await startAgain(
        `Apertus is sorting your bookings again, now with “${name}”.`,
      );
    } catch (failure) {
      setError(
        `“${name}” was added, but Apertus did not start sorting again. ${requestErrorOf(failure).message}`,
      );
    } finally {
      setBusyId(null);
    }
    return true;
  }

  async function changeNecessity(category: string, severity: string) {
    setBusyId("necessity");
    setError(null);
    try {
      await setNecessity(token, category, severity);
      await reload();
    } catch (failure) {
      setError(
        `${labelOf(category)} was not changed. ${requestErrorOf(failure).message}`,
      );
    } finally {
      setBusyId(null);
    }
  }

  async function retry() {
    setError(null);
    try {
      setRun(
        await api<CategorisationRun>("/api/categorisations", token, json({})),
      );
    } catch (failure) {
      setError(requestErrorOf(failure).message);
    }
  }

  if (loadError !== null)
    return (
      <div className="state" role="alert">
        <h1>Your categories did not load</h1>
        <p>{loadError}</p>
      </div>
    );
  if (loaded === null)
    return (
      <div className="state" aria-live="polite">
        <span className="spinner" aria-hidden="true" />
        <p>Loading your categories…</p>
      </div>
    );

  const decisions = decisionsOf(loaded.rows).filter(
    (decision) => !decided.has(decision.id),
  );
  const going = isGoing(run);

  return (
    <div className="cat-view">
      <button type="button" className="cat-back" onClick={onBack}>
        <span aria-hidden="true">←</span> Personalized Board
      </button>
      <header className="cat-head">
        <div>
          <h1>Categorization</h1>
          <p className="hint">
            Settle the categories Apertus was unsure of. Every answer also
            teaches it for your next bookings.
          </p>
        </div>
        <div className="mode" role="group" aria-label="What to show">
          <button
            type="button"
            aria-pressed={view === "decide"}
            onClick={() => setView("decide")}
          >
            To decide ({decisions.length})
          </button>
          <button
            type="button"
            aria-pressed={view === "overview"}
            onClick={() => setView("overview")}
          >
            Overview
          </button>
        </div>
      </header>

      {going && run !== null && (
        <div className="cat-banner cat-progress" aria-live="polite">
          <div className="cat-progress-text">
            <span>
              {notice ??
                "Apertus is sorting your bookings. New decisions show up here when it is done."}
            </span>
            <b className="num">{run.progress} %</b>
          </div>
          <div
            className="cat-progress-track"
            role="progressbar"
            aria-label="Sorting your bookings"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={run.progress}
          >
            <span style={{ width: `${run.progress}%` }} />
          </div>
          <small className="hint">{stepText(run)}</small>
        </div>
      )}
      {run?.status === "failed" && (
        <p className="cat-banner" data-tone="warn" role="alert">
          Sorting your bookings stopped before the end.
          <button type="button" className="button" onClick={() => void retry()}>
            Try again
          </button>
        </p>
      )}
      {error !== null && (
        <p className="error-note" role="alert">
          {error}
        </p>
      )}

      {view === "overview" ? (
        <Overview
          loaded={loaded}
          isBusy={busyId !== null}
          onAddCategory={(name, description) =>
            add("category", name, description)
          }
          onAddTag={(name, description) => add("tag", name, description)}
          onNecessity={(category, severity) =>
            void changeNecessity(category, severity)
          }
        />
      ) : decisions.length === 0 ? (
        <div className="state cat-done">
          <h2>{going ? "Nothing to decide yet" : "Nothing left to decide"}</h2>
          <p className="hint">
            {going
              ? "Apertus is still sorting. What it is unsure of lands here."
              : `Apertus is sure of all ${loaded.rows.length} categorised bookings, or you have settled them.`}
          </p>
        </div>
      ) : (
        <>
          <div className="cat-toolbar">
            <div className="mode" role="group" aria-label="How to decide">
              <button
                type="button"
                aria-pressed={layout === "list"}
                onClick={() => chooseLayout("list")}
              >
                List
              </button>
              <button
                type="button"
                aria-pressed={layout === "swipe"}
                onClick={() => chooseLayout("swipe")}
              >
                Swipe
              </button>
            </div>
          </div>
          {layout === "swipe" ? (
            <SwipeDeck
              decisions={decisions}
              categories={loaded.categories}
              busyId={busyId}
              onChoose={(decision, category) => void choose(decision, category)}
              onCreate={(decision, name, description) =>
                void createAndChoose(decision, name, description)
              }
            />
          ) : (
            <DecisionList
              decisions={decisions}
              categories={loaded.categories}
              busyId={busyId}
              onChoose={(decision, category) => void choose(decision, category)}
              onCreate={(decision, name, description) =>
                void createAndChoose(decision, name, description)
              }
            />
          )}
        </>
      )}
    </div>
  );
}
