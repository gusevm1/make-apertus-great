import { useEffect, useState } from "react";
import { api, json, type RequestError, requestErrorOf } from "../api";
import { ALERTS_CHANGED } from "./NeedsAttention";

interface AlertSetting {
  kind: "invoice";
  enabled: boolean;
}

const LABELS: Record<AlertSetting["kind"], string> = {
  invoice: "Unpaid invoices and reminders",
};

/** The profile's Alerts section: one switch per check the TrustRoom runs. */
export function AlertSettings({ token }: { token: string }) {
  const [settings, setSettings] = useState<AlertSetting[] | null>(null);
  const [error, setError] = useState<RequestError | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setSettings(await api<AlertSetting[]>("/api/alert-settings", token));
    } catch (problem) {
      setError(requestErrorOf(problem));
    }
  }

  useEffect(() => {
    void load();
    const reload = () => void load();
    window.addEventListener(ALERTS_CHANGED, reload);
    return () => window.removeEventListener(ALERTS_CHANGED, reload);
  }, [token]);

  async function toggle(setting: AlertSetting) {
    setFailure(null);
    try {
      await api(`/api/alert-settings/${setting.kind}`, token, {
        ...json({ enabled: !setting.enabled }),
        method: "PATCH",
      });
      window.dispatchEvent(new Event(ALERTS_CHANGED));
    } catch (problem) {
      setFailure(requestErrorOf(problem).message);
    }
  }

  return (
    <div className="sec">
      <h2>Alerts</h2>
      <div className="card">
        {error !== null && (
          <div className="failure" role="alert">
            <p>
              <strong>{error.message}</strong>
              Your alerts were not loaded.
            </p>
            <button type="button" onClick={() => void load()}>
              Try again
            </button>
          </div>
        )}
        {error === null && settings === null && (
          <p className="hint">Loading…</p>
        )}
        {settings?.map((setting) => (
          <label key={setting.kind} className="fact alert-setting">
            <p>{LABELS[setting.kind]}</p>
            <input
              type="checkbox"
              checked={setting.enabled}
              onChange={() => void toggle(setting)}
            />
          </label>
        ))}
        {failure !== null && (
          <p className="hint" role="alert">
            Not changed. {failure}
          </p>
        )}
      </div>
    </div>
  );
}
