import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

const apiMocks = vi.hoisted(() => ({
  useReadiness: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  useReadiness: apiMocks.useReadiness,
}));

import { EmbedCodePanel } from "./EmbedCodePanel";

const EMBED =
  '<div data-magnit-embed><iframe data-magnit-frame src="https://magai-widget-abc123.vercel.app" ' +
  'width="100%"></iframe></div><script>/* magnit:resize */</script>';
const URL = "https://magai-widget-abc123.vercel.app";

describe("EmbedCodePanel", () => {
  it("verifies the installation against real readiness state", async () => {
    const refetch = vi.fn().mockResolvedValue({
      data: { checks: [{ id: "embedded", done: true }] },
      error: null,
    });
    apiMocks.useReadiness.mockReturnValue({ refetch, isFetching: false });

    render(<EmbedCodePanel widgetId="w1" embedCode={EMBED} embedUrl={URL} />);
    await userEvent.click(screen.getByRole("button", { name: /verify installation/i }));

    expect(refetch).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("status")).toHaveTextContent("Installation detected");
  });

  it("shows the snippet the customer needs to paste", () => {
    const { container } = render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
    // Scoped to the <code> block so the assertion is about the snippet itself
    // rather than any other place the URL happens to be rendered.
    const snippet = container.querySelector("code");
    expect(snippet).toHaveTextContent("magai-widget-abc123.vercel.app");
    expect(snippet).toHaveTextContent("<iframe");
  });

  it("tells the customer the snippet is a one-time paste", () => {
    // The whole value of a hosted widget is that the embed never has to change,
    // so the panel has to say so where the customer is about to copy it.
    render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
    expect(screen.getByText(/never changes/i)).toBeInTheDocument();
  });

  it("tells the owner where the generated strategy says the tool belongs", () => {
    render(
      <EmbedCodePanel
        embedCode={EMBED}
        embedUrl={URL}
        recommendedPlacement="New patients page"
        targetUrl="https://northside.example/new-patients"
      />,
    );

    expect(screen.getByText(/recommended placement: new patients page/i)).toBeInTheDocument();
    expect(screen.getByText(/northside\.example\/new-patients/i)).toBeInTheDocument();
  });

  it("prompts a deploy when there is nothing to embed yet", () => {
    render(<EmbedCodePanel embedCode={null} embedUrl={null} />);
    expect(screen.getByText(/once this is published/i)).toBeInTheDocument();
  });

  it("copies the snippet and confirms", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });

    render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));

    expect(writeText).toHaveBeenCalledWith(EMBED);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("survives a denied clipboard permission", async () => {
    // Clipboard access fails in insecure contexts; the snippet is still
    // selectable in the <pre>, so this must degrade rather than throw.
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });

    render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));

    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });

  it("opens the live widget in a new tab safely", () => {
    render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
    const link = screen.getByRole("link", { name: /open live/i });
    expect(link).toHaveAttribute("href", URL);
    // noopener prevents the opened page from reaching back via window.opener.
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  /**
   * Every platform tab has to behave the same once it is on a real page.
   *
   * Four of the five used to be hand-written iframes fixed at 640px while only
   * the HTML tab grew with its content — so a Webflow or Shopify customer got a
   * result panel cut off mid-sentence on a phone, and nothing in the product
   * ever said so. The fix is structural: the HTML-accepting platforms share one
   * snippet rather than four near-copies.
   */
  describe("platform parity", () => {
    it.each(["Webflow", "WordPress", "Shopify"])(
      "gives %s the same snippet as HTML",
      async (label) => {
        const { container } = render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
        await userEvent.click(screen.getByRole("tab", { name: label }));

        const snippet = container.querySelector("code")?.textContent ?? "";
        expect(snippet).toContain(EMBED);
      },
    );

    it("gives React its own component that still resizes", async () => {
      const { container } = render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
      await userEvent.click(screen.getByRole("tab", { name: /react/i }));

      const snippet = container.querySelector("code")?.textContent ?? "";
      expect(snippet).toContain("magnit:resize");
      // The same origin and source checks the HTML snippet makes, so the React
      // path is not the quietly less careful one.
      expect(snippet).toContain("event.source !== frame.current?.contentWindow");
      expect(snippet).toContain(`const TOOL_ORIGIN = "${URL}"`);
      expect(snippet).not.toContain('height="640"');
    });

    it("never hands out the URL of a single build", async () => {
      // deployment_url changes on every publish; embed_url does not. Pasting
      // the former onto a customer's website is the bug this panel exists to
      // avoid, and it is invisible until their page silently goes stale.
      const { container } = render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
      for (const label of ["React / Next.js", "Webflow", "WordPress", "Shopify", "HTML"]) {
        await userEvent.click(screen.getByRole("tab", { name: label }));
        const snippet = container.querySelector("code")?.textContent ?? "";
        expect(snippet).toContain(URL);
      }
    });
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<EmbedCodePanel embedCode={EMBED} embedUrl={URL} />);
    await expectNoA11yViolations(container);
  });
});
