import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "@/test/a11y";

import { VerifyEmailNotice } from "./VerifyEmailNotice";

/**
 * Unverified email is the only requirement in the build flow that the customer
 * cannot satisfy on the screen they are looking at. These tests hold the notice
 * to the property that makes it worth showing: it carries a working remedy, and
 * says what happened when the remedy is used.
 */
afterEach(() => {
  vi.unstubAllGlobals();
});

function ok() {
  return vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
}

describe("VerifyEmailNotice", () => {
  it("names the address that needs confirming", () => {
    render(<VerifyEmailNotice email="owner@example.com" />);
    expect(screen.getByText(/owner@example\.com/)).toBeInTheDocument();
  });

  it("resends the verification email through the API", async () => {
    const fetchMock = ok();
    vi.stubGlobal("fetch", fetchMock);

    render(<VerifyEmailNotice email="owner@example.com" />);
    await userEvent.click(screen.getByRole("button", { name: /resend/i }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/auth/resend-verification");
    expect(await screen.findByText(/new link sent/i)).toBeInTheDocument();
  });

  it("cannot be pressed twice, so a customer does not fan out links", async () => {
    const fetchMock = ok();
    vi.stubGlobal("fetch", fetchMock);

    render(<VerifyEmailNotice email="owner@example.com" />);
    const button = screen.getByRole("button", { name: /resend/i });
    await userEvent.click(button);
    await screen.findByText(/new link sent/i);

    expect(screen.getByRole("button", { name: /sent/i })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("admits a failure rather than claiming a link was sent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "rate_limit_exceeded" }), {
          status: 429,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    render(<VerifyEmailNotice email="owner@example.com" />);
    await userEvent.click(screen.getByRole("button", { name: /resend/i }));

    expect(await screen.findByText(/couldn't send/i)).toBeInTheDocument();
    // Still offered, because the customer is not out of options.
    expect(screen.getByRole("button", { name: /resend/i })).toBeEnabled();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<VerifyEmailNotice email="owner@example.com" />);
    await expectNoA11yViolations(container);
  });
});
