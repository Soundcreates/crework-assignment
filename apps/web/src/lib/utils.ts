import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { IntentLevel, SignalType } from "@/types/company";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function intentBadgeClass(level: IntentLevel): string {
  switch (level) {
    case "HIGH":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 dark:border dark:border-emerald-800/60";
    case "MEDIUM HIGH":
      return "bg-sky-100 text-sky-800 dark:bg-sky-950/70 dark:text-sky-300 dark:border dark:border-sky-800/60";
    case "MEDIUM":
      return "bg-amber-100 text-amber-900 dark:bg-amber-950/70 dark:text-amber-300 dark:border dark:border-amber-800/60";
    default:
      return "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:border dark:border-zinc-700/60";
  }
}

export function signalLabel(type: SignalType): string {
  return type.replaceAll("_", " ");
}
