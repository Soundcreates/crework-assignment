import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { IntentLevel, SignalType } from "@/types/company";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function intentBadgeClass(level: IntentLevel): string {
  switch (level) {
    case "HIGH":
      return "bg-emerald-100 text-emerald-800";
    case "MEDIUM HIGH":
      return "bg-sky-100 text-sky-800";
    case "MEDIUM":
      return "bg-amber-100 text-amber-900";
    default:
      return "bg-zinc-100 text-zinc-700";
  }
}

export function signalLabel(type: SignalType): string {
  return type.replaceAll("_", " ");
}
