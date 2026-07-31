import type { WidgetData } from "@/lib/api";
import { liveAddress } from "@/lib/widget-url";

/**
 * What actually happened when the owner pressed Save.
 *
 * Both editors used to say "Live on your tool now" unconditionally, which was
 * wrong twice: for a tool that has never been published there is nothing live to
 * be on, and even for a published one the deployed widget reads its
 * configuration through a short edge cache, so "now" overstates it by up to a
 * minute. Someone who opens their own page to check and sees the old wording
 * concludes the product does not work — the fix is to say the true thing, which
 * is still a good thing.
 */
export function SaveConfirmation({ widget }: { widget: WidgetData }) {
  const published = Boolean(liveAddress(widget)) && widget.status === "active";

  return (
    <span aria-live="polite" className="text-xs text-success">
      {published ? "Saved · live within a minute" : "Saved · ready for publish"}
    </span>
  );
}
