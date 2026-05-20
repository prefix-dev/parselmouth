import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api/r2";
