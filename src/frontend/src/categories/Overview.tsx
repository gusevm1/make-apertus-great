import { type FormEvent, useState } from "react";
import { chf, labelOf, type Loaded, NECESSITIES } from "./data";

/** What a category counts as: the customer's or Apertus's rating, else what its rows say. */
function necessityOf(loaded: Loaded, category: string): string {
  const setting = loaded.severities.find(
    (item) => item.scope === "category" && item.key === category,
  );
  if (setting !== undefined) return setting.severity;
  const row = loaded.rows.find((item) => item.category === category);
  return row?.severity ?? "moderate";
}

function AddForm({
  label,
  namePlaceholder,
  descriptionPlaceholder,
  isBusy,
  onAdd,
}: {
  label: string;
  namePlaceholder: string;
  descriptionPlaceholder: string;
  isBusy: boolean;
  onAdd: (name: string, description: string) => Promise<boolean>;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim() === "") return;
    if (await onAdd(name.trim(), description.trim())) {
      setName("");
      setDescription("");
      setIsOpen(false);
    }
  }

  if (!isOpen)
    return (
      <button
        type="button"
        className="button cat-add"
        onClick={() => setIsOpen(true)}
      >
        + {label}
      </button>
    );
  return (
    <form className="cat-new" onSubmit={(event) => void submit(event)}>
      <label>
        <span>Name</span>
        <input
          value={name}
          maxLength={40}
          placeholder={namePlaceholder}
          autoFocus
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <label>
        <span>What belongs in it (helps Apertus)</span>
        <input
          value={description}
          maxLength={200}
          placeholder={descriptionPlaceholder}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>
      <div className="cat-options">
        <button
          type="submit"
          className="button go"
          disabled={isBusy || name.trim() === ""}
        >
          Add, and let Apertus sort again
        </button>
        <button
          type="button"
          className="button"
          onClick={() => setIsOpen(false)}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export function Overview({
  loaded,
  isBusy,
  onAddCategory,
  onAddTag,
  onNecessity,
}: {
  loaded: Loaded;
  isBusy: boolean;
  onAddCategory: (name: string, description: string) => Promise<boolean>;
  onAddTag: (name: string, description: string) => Promise<boolean>;
  onNecessity: (category: string, severity: string) => void;
}) {
  const summaries = new Map(
    loaded.summaries.map((summary) => [summary.category, summary]),
  );
  const categories = loaded.categories.map((category) => {
    const summary = summaries.get(category.name);
    return {
      ...category,
      total: summary === undefined ? 0 : Number(summary.total_chf),
      count: summary?.row_count ?? 0,
      unsure:
        summary === undefined
          ? 0
          : summary.low + summary.medium + summary.unknown,
      necessity: necessityOf(loaded, category.name),
    };
  });
  const uncategorised = summaries.get(null);

  return (
    <div className="cat-overview">
      <section aria-labelledby="cat-necessity">
        <h2 id="cat-necessity">Necessity</h2>
        <p className="hint">
          How much you can do without each kind of spending, over the whole
          history. Saving suggestions start at the bottom.
        </p>
        <ul className="cat-levels">
          {NECESSITIES.map((level) => {
            const members = categories.filter(
              (category) =>
                category.necessity === level.key && category.count > 0,
            );
            const total = members.reduce((sum, item) => sum + item.total, 0);
            return (
              <li key={level.key}>
                <div className="cat-level-head">
                  <b>{level.label}</b>
                  <span className="num">{chf.format(total)}</span>
                </div>
                <p className="hint">
                  {members.length === 0
                    ? "No category"
                    : members.map((item) => labelOf(item.name)).join(", ")}
                </p>
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="cat-spending">
        <h2 id="cat-spending">Spending categories</h2>
        <table className="cat-table">
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col" className="num">
                Spent
              </th>
              <th scope="col" className="num">
                Bookings
              </th>
              <th scope="col">Necessity</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((category) => (
              <tr key={category.name}>
                <th scope="row">
                  {labelOf(category.name)}
                  {category.custom && <span className="cat-own">yours</span>}
                  {category.unsure > 0 && (
                    <small className="hint">{category.unsure} unsure</small>
                  )}
                </th>
                <td className="num">{chf.format(category.total)}</td>
                <td className="num">{category.count}</td>
                <td>
                  <select
                    aria-label={`Necessity of ${labelOf(category.name)}`}
                    value={category.necessity}
                    disabled={isBusy}
                    onChange={(event) =>
                      onNecessity(category.name, event.target.value)
                    }
                  >
                    {NECESSITIES.map((level) => (
                      <option key={level.key} value={level.key}>
                        {level.label}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {uncategorised !== undefined && (
          <p className="hint">
            {uncategorised.row_count} bookings (
            {chf.format(Number(uncategorised.total_chf))}) have no category yet.
          </p>
        )}
        <AddForm
          label="Add a spending category"
          namePlaceholder="e.g. Pets"
          descriptionPlaceholder="e.g. Cat food, vet, pet shop"
          isBusy={isBusy}
          onAdd={onAddCategory}
        />
      </section>

      <section aria-labelledby="cat-personal">
        <h2 id="cat-personal">Personal tags</h2>
        <p className="hint">
          Your own groups across categories, such as a trip or a child. A
          booking can carry several.
        </p>
        {loaded.tags.length === 0 ? (
          <p className="hint">No personal tag yet.</p>
        ) : (
          <ul className="cat-tags">
            {loaded.tags.map((tag) => (
              <li key={tag.id}>
                <div className="cat-level-head">
                  <b>{tag.name}</b>
                  <span className="num">
                    {chf.format(Number(tag.spending_total_chf))}
                  </span>
                </div>
                <p className="hint">
                  {tag.spending_count} bookings
                  {tag.description === "" ? "" : ` · ${tag.description}`}
                </p>
              </li>
            ))}
          </ul>
        )}
        <AddForm
          label="Add a personal tag"
          namePlaceholder="e.g. Japan trip"
          descriptionPlaceholder="e.g. Flights, hotels and spending in Japan"
          isBusy={isBusy}
          onAdd={onAddTag}
        />
      </section>
    </div>
  );
}
