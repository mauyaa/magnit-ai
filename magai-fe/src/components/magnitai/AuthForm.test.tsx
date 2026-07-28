import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/lib/auth";
import { expectNoA11yViolations } from "@/test/a11y";

import { AuthForm } from "./AuthForm";

function wrap(children: ReactNode) {
  // Retries off: a failed mutation should surface immediately in tests.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

function renderForm(mode: "login" | "signup" = "login") {
  const onSuccess = vi.fn();
  const onSwitchMode = vi.fn();
  const result = render(
    wrap(<AuthForm mode={mode} onSuccess={onSuccess} onSwitchMode={onSwitchMode} />),
  );
  return { ...result, onSuccess, onSwitchMode };
}

describe("AuthForm", () => {
  it("renders labelled email and password fields", () => {
    renderForm();
    // Labels, not placeholders: a placeholder is not an accessible name.
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in with google/i })).toBeInTheDocument();
  });

  it("offers Google signup in create-account mode", () => {
    renderForm("signup");
    expect(screen.getByRole("button", { name: /sign up with google/i })).toBeInTheDocument();
  });

  it("uses autocomplete tokens password managers understand", () => {
    renderForm("signup");
    expect(screen.getByLabelText(/email/i)).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText(/password/i)).toHaveAttribute("autocomplete", "new-password");
  });

  it("uses current-password on the login form", () => {
    renderForm("login");
    expect(screen.getByLabelText(/password/i)).toHaveAttribute("autocomplete", "current-password");
  });

  it("rejects a malformed email before calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderForm();
    await userEvent.type(screen.getByLabelText(/email/i), "not-an-email");
    await userEvent.type(screen.getByLabelText(/password/i), "correct-horse-battery-99");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/valid email/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("enforces the password policy on signup only", async () => {
    vi.stubGlobal("fetch", vi.fn());

    renderForm("signup");
    await userEvent.type(screen.getByLabelText(/email/i), "new@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "short1");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/at least 12 characters/i);
  });

  it("marks invalid fields for assistive technology", async () => {
    renderForm();
    await userEvent.type(screen.getByLabelText(/email/i), "bad");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(screen.getByLabelText(/email/i)).toHaveAttribute("aria-invalid", "true");
  });

  it("surfaces a server error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "invalid_credentials" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    renderForm();
    await userEvent.type(screen.getByLabelText(/email/i), "user@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-passw0rd-here");
    await userEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/don't match/i);
  });

  it("switches between sign-in and sign-up", async () => {
    const { onSwitchMode } = renderForm();
    await userEvent.click(screen.getByRole("button", { name: /create an account/i }));
    expect(onSwitchMode).toHaveBeenCalled();
  });

  it("has no accessibility violations on the login form", async () => {
    const { container } = renderForm("login");
    await expectNoA11yViolations(container);
  });

  it("has no accessibility violations on the signup form", async () => {
    const { container } = renderForm("signup");
    await expectNoA11yViolations(container);
  });
});
