import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { EmbedCodePanel } from "./EmbedCodePanel";

const EMBED = '<iframe src="https://magai-widget-abc123.vercel.app" width="100%"></iframe>';
const URL = "https://magai-widget-abc123.vercel.app";

describe("EmbedCodePanel", () => {
  it("shows the snippet the customer needs to paste", () => {
    const { container } = render(<EmbedCodePanel embedCode={EMBED} deploymentUrl={URL} />);
    // Scoped to the <code> block so the assertion is about the snippet itself
    // rather than any other place the URL happens to be rendered.
    const snippet = container.querySelector("code");
    expect(snippet).toHaveTextContent("magai-widget-abc123.vercel.app");
    expect(snippet).toHaveTextContent("<iframe");
  });

  it("tells the customer the snippet is a one-time paste", () => {
    // The whole value of a hosted widget is that the embed never has to change,
    // so the panel has to say so where the customer is about to copy it.
    render(<EmbedCodePanel embedCode={EMBED} deploymentUrl={URL} />);
    expect(screen.getByText(/never changes/i)).toBeInTheDocument();
  });

  it("prompts a deploy when there is nothing to embed yet", () => {
    render(<EmbedCodePanel embedCode={null} deploymentUrl={null} />);
    expect(screen.getByText(/once this is published/i)).toBeInTheDocument();
  });

  it("copies the snippet and confirms", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });

    render(<EmbedCodePanel embedCode={EMBED} deploymentUrl={URL} />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));

    expect(writeText).toHaveBeenCalledWith(EMBED);
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("survives a denied clipboard permission", async () => {
    // Clipboard access fails in insecure contexts; the snippet is still
    // selectable in the <pre>, so this must degrade rather than throw.
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });

    render(<EmbedCodePanel embedCode={EMBED} deploymentUrl={URL} />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));

    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });

  it("opens the live widget in a new tab safely", () => {
    render(<EmbedCodePanel embedCode={EMBED} deploymentUrl={URL} />);
    const link = screen.getByRole("link", { name: /open live/i });
    expect(link).toHaveAttribute("href", URL);
    // noopener prevents the opened page from reaching back via window.opener.
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<EmbedCodePanel embedCode={EMBED} deploymentUrl={URL} />);
    await expectNoA11yViolations(container);
  });
});
