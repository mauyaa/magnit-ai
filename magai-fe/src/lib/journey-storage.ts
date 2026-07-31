import type { GuestConceptsResponse } from "@/lib/api";

export const JOURNEY_STORAGE_KEY = "magnitai:first-look";

export interface SavedJourney extends GuestConceptsResponse {
  selectedIndex: number | null;
  widgetId: string | null;
}

export function journeyDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url.replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
  }
}

export function loadSavedJourney(): SavedJourney | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(JOURNEY_STORAGE_KEY) ?? "null",
    ) as SavedJourney;
    if (
      !parsed ||
      !parsed.session_token ||
      !Array.isArray(parsed.concepts) ||
      parsed.concepts.length < 1 ||
      parsed.concepts.length > 2
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveJourney(journey: SavedJourney | null): void {
  if (typeof window === "undefined") return;
  if (journey) {
    window.sessionStorage.setItem(JOURNEY_STORAGE_KEY, JSON.stringify(journey));
  } else {
    window.sessionStorage.removeItem(JOURNEY_STORAGE_KEY);
  }
}
