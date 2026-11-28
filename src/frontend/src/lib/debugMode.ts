import { useSyncExternalStore } from "react";

const STORAGE_KEY = "trustroom:debug-mode";
const DEBUG_MODE_CHANGED = "trustroom:debug-mode-changed";

function isDebugMode() {
  try {
    return localStorage.getItem(STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(DEBUG_MODE_CHANGED, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(DEBUG_MODE_CHANGED, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Sets whether the page shows the agent trace, kept in this browser. */
export function setDebugMode({ isOn }: { isOn: boolean }) {
  try {
    if (isOn) localStorage.setItem(STORAGE_KEY, "on");
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Without storage debug mode stays off.
  }
  window.dispatchEvent(new Event(DEBUG_MODE_CHANGED));
}

/** Whether the customer turned on debug mode, which shows the plans and tool calls behind each answer. */
export function useDebugMode() {
  return useSyncExternalStore(subscribe, isDebugMode, isDebugMode);
}
