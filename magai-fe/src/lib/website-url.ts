const PROTOCOL = /^https?:\/\//i;

/**
 * Turn the way a person naturally types a website into the canonical URL sent
 * to the analyzer. Every entry point uses this function so the landing page,
 * empty workspace, and builder never disagree about what a valid site is.
 */
export function normalizeWebsiteUrl(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;

  try {
    const url = new URL(PROTOCOL.test(value) ? value : `https://${value}`);
    if (!url.hostname.includes(".") || url.username || url.password) return null;
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}

export function websiteFieldValue(raw: string): string {
  return raw.trim().replace(PROTOCOL, "").replace(/\/+$/, "");
}
