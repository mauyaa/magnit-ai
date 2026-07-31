/**
 * The address to show an owner when we mean "your tool".
 *
 * A published tool has two URLs and they are not interchangeable.
 * `deployment_url` is one particular build and changes every publish;
 * `embed_url` is the permanent address inside the snippet on their website. The
 * owner should always be looking at the second one — it is what their visitors
 * reach, and what the product promises will not change.
 *
 * The fallback covers tools published before permanent addresses existed, whose
 * `embed_url` is still null until their next publish.
 */
export function liveAddress(widget: {
  embed_url?: string | null;
  deployment_url?: string | null;
}): string | null {
  return widget.embed_url ?? widget.deployment_url ?? null;
}
