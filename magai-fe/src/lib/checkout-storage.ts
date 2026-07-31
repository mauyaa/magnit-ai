/**
 * The one fact that has to survive the trip to Stripe and back.
 *
 * Opening checkout marks the tool `checkout_pending`, which disables the build
 * button. Only the payment provider could clear that, so pressing "back" on the
 * payment page returned the customer to a tool they could no longer build. To
 * ask Stripe what actually happened we need the session id — and Stripe only
 * substitutes it into the success URL, never the cancel URL. So we keep it
 * ourselves, in the tab that is going to come back.
 */
const PENDING_CHECKOUT_KEY = "magnitai:pending-checkout";

export interface PendingCheckout {
  sessionId: string;
  kind: "one_time" | "subscription";
  /** Which tool the customer was paying for, so a lost journey can be re-found. */
  widgetId: string | null;
}

export function rememberPendingCheckout(pending: PendingCheckout): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(PENDING_CHECKOUT_KEY, JSON.stringify(pending));
  } catch {
    // Storage can be unavailable (private mode, quota). Reconciliation is a
    // recovery path, not the primary one — the webhook still settles this.
  }
}

export function loadPendingCheckout(): PendingCheckout | null {
  if (typeof window === "undefined") return null;
  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(PENDING_CHECKOUT_KEY) ?? "null",
    ) as PendingCheckout | null;
    if (!parsed?.sessionId || (parsed.kind !== "one_time" && parsed.kind !== "subscription")) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearPendingCheckout(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(PENDING_CHECKOUT_KEY);
  } catch {
    /* see above */
  }
}
