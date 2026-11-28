import { type FormEvent, useState } from "react";
import { labelOf, type SpendingCategory } from "./data";

/** The pen's panel: any existing category, or a new one with a short description. */
export function CategoryPicker({
  categories,
  exclude,
  isBusy,
  onPick,
  onCreate,
  onClose,
}: {
  categories: SpendingCategory[];
  exclude: string[];
  isBusy: boolean;
  onPick: (category: string) => void;
  onCreate: (name: string, description: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const choices = categories.filter(
    (category) => !exclude.includes(category.name),
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim() === "") return;
    onCreate(name.trim(), description.trim());
  }

  return (
    <div className="cat-picker" role="group" aria-label="Another category">
      <div className="cat-picker-head">
        <b>Another category</b>
        <button
          type="button"
          className="cat-icon-button"
          aria-label="Close"
          onClick={onClose}
        >
          ×
        </button>
      </div>
      <div className="cat-chips">
        {choices.map((category) => (
          <button
            key={category.name}
            type="button"
            className="cat-chip"
            disabled={isBusy}
            onClick={() => onPick(category.name)}
          >
            {labelOf(category.name)}
          </button>
        ))}
      </div>
      <form className="cat-new" onSubmit={submit}>
        <label>
          <span>New category</span>
          <input
            value={name}
            maxLength={40}
            placeholder="e.g. Pets"
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          <span>What belongs in it (helps Apertus)</span>
          <input
            value={description}
            maxLength={200}
            placeholder="e.g. Cat food, vet, pet shop"
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <button
          type="submit"
          className="button go"
          disabled={isBusy || name.trim() === ""}
        >
          Add and use
        </button>
      </form>
    </div>
  );
}
