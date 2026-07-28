import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/lib/auth";

type GoogleMode = "login" | "signup";

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdentityApi {
  initialize: (options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    auto_select?: boolean;
    cancel_on_tap_outside?: boolean;
  }) => void;
  renderButton: (
    parent: HTMLElement,
    options: {
      type: "standard";
      theme: "outline";
      size: "large";
      text: "signin_with" | "signup_with";
      shape: "rectangular";
      width: number;
    },
  ) => void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentityApi } };
  }
}

const GOOGLE_SCRIPT_ID = "google-identity-services";
let googleScriptPromise: Promise<void> | null = null;

function loadGoogleIdentityServices(): Promise<void> {
  if (window.google?.accounts.id) return Promise.resolve();
  if (googleScriptPromise) return googleScriptPromise;

  googleScriptPromise = new Promise((resolve, reject) => {
    const existing = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error("Google sign-in is unavailable.")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Google sign-in is unavailable."));
    document.head.appendChild(script);
  });

  return googleScriptPromise;
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 18 18" className="size-[18px]" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M17.64 9.205c0-.638-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.797 2.716v2.259h2.909c1.703-1.568 2.684-3.878 2.684-6.615Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.909-2.259c-.806.54-1.835.859-3.047.859-2.344 0-4.328-1.585-5.037-3.714H.957v2.332A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.963 10.706A5.41 5.41 0 0 1 3.682 9c0-.592.102-1.168.281-1.706V4.962H.957A9 9 0 0 0 0 9c0 1.452.347 2.827.957 4.038l3.006-2.332Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.321 0 2.507.454 3.441 1.346l2.581-2.581C13.463.892 11.426 0 9 0A9 9 0 0 0 .957 4.962l3.006 2.332C4.672 5.165 6.656 3.58 9 3.58Z"
      />
    </svg>
  );
}

export function GoogleAuthButton({
  mode,
  onSuccess,
  onError,
  disabled = false,
}: {
  mode: GoogleMode;
  onSuccess: () => void;
  onError: (message: string) => void;
  disabled?: boolean;
}) {
  const { googleLogin } = useAuth();
  const mountRef = useRef<HTMLDivElement>(null);
  const callbackRef = useRef<(credential: string) => void>(() => undefined);
  const [scriptError, setScriptError] = useState(false);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();

  callbackRef.current = (credential) => {
    googleLogin.mutate(
      { credential },
      {
        onSuccess,
        onError: (error) =>
          onError(error instanceof Error ? error.message : "Google sign-in failed."),
      },
    );
  };

  useEffect(() => {
    if (!clientId || !mountRef.current) return;
    let cancelled = false;
    const mount = mountRef.current;

    const render = () => {
      if (cancelled || !window.google?.accounts.id) return;
      mount.replaceChildren();
      window.google.accounts.id.renderButton(mount, {
        type: "standard",
        theme: "outline",
        size: "large",
        text: mode === "signup" ? "signup_with" : "signin_with",
        shape: "rectangular",
        width: Math.max(240, Math.floor(mount.clientWidth)),
      });
    };

    void loadGoogleIdentityServices()
      .then(() => {
        if (cancelled || !window.google?.accounts.id) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => callbackRef.current(response.credential),
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        render();
      })
      .catch(() => {
        if (!cancelled) {
          setScriptError(true);
          onError("Google sign-in is temporarily unavailable.");
        }
      });

    const resize = new ResizeObserver(render);
    resize.observe(mount);
    return () => {
      cancelled = true;
      resize.disconnect();
    };
  }, [clientId, mode, onError]);

  if (!clientId || scriptError) {
    return (
      <button
        type="button"
        disabled
        title={
          clientId
            ? "Google sign-in is temporarily unavailable."
            : "Google sign-in needs a client ID."
        }
        className="flex h-11 w-full items-center justify-center gap-3 rounded-xl border border-border-strong bg-card text-sm font-medium text-foreground opacity-60"
      >
        <GoogleMark />
        {mode === "signup" ? "Sign up with Google" : "Sign in with Google"}
      </button>
    );
  }

  return (
    <div
      className={`relative min-h-11 overflow-hidden rounded-xl ${
        disabled || googleLogin.isPending ? "pointer-events-none opacity-60" : ""
      }`}
      aria-busy={googleLogin.isPending}
    >
      <div ref={mountRef} className="min-h-11 w-full [&>div]:mx-auto" />
      {googleLogin.isPending ? (
        <div className="absolute inset-0 grid place-items-center bg-card/90">
          <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Signing in" />
        </div>
      ) : null}
    </div>
  );
}
