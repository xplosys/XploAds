"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

export type ThemePreference = "light" | "dark" | "system";
const STORAGE_KEY = "xploads.theme";
const listeners = new Set<() => void>();

/**
 * Runs before first paint (inlined in <head>) so the page never flashes the wrong theme.
 * Keep in sync with applyTheme below.
 */
export const themeInitScript = `(function(){try{var p=localStorage.getItem("${STORAGE_KEY}")||"system";var d=p==="dark"||(p==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches);var r=document.documentElement;r.classList.toggle("dark",d);r.style.colorScheme=d?"dark":"light";}catch(e){}})();`;

function readPreference(): ThemePreference {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(pref: ThemePreference) {
  const dark = pref === "dark" || (pref === "system" && systemDark());
  const root = document.documentElement;
  root.classList.toggle("dark", dark);
  root.style.colorScheme = dark ? "dark" : "light";
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystem = () => {
    if (readPreference() === "system") applyTheme("system");
    listener();
  };
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      applyTheme(readPreference());
      listener();
    }
  };
  media.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage); // keep other tabs in sync
  return () => {
    listeners.delete(listener);
    media.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
  };
}

export function setTheme(pref: ThemePreference) {
  try {
    window.localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    // storage blocked: still apply for this page view
  }
  applyTheme(pref);
  listeners.forEach((l) => l());
}

/** Current preference and the theme actually shown. */
export function useTheme() {
  const preference = useSyncExternalStore(subscribe, readPreference, () => "system" as ThemePreference);
  const resolved = useSyncExternalStore(
    subscribe,
    (): "light" | "dark" => (document.documentElement.classList.contains("dark") ? "dark" : "light"),
    () => "light" as const,
  );
  return { preference, resolved, setTheme };
}

/**
 * One icon button: a moon in light mode (switch to dark) and a sun in dark mode (switch to light).
 * Until the user clicks it the app follows the operating-system setting.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolved } = useTheme();
  const next = resolved === "dark" ? "light" : "dark";
  const Icon = resolved === "dark" ? Sun : Moon;
  const label = `Switch to ${next} mode`;
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex size-8 items-center justify-center rounded-md border bg-card text-muted-foreground hover:bg-muted hover:text-foreground",
        className,
      )}
    >
      <Icon className="size-4" aria-hidden />
    </button>
  );
}
