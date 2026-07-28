import { Link } from "@tanstack/react-router";
import { ArrowLeft, ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { MarketingFooter } from "./MarketingFooter";

interface LegalPageProps {
  title: string;
  updated: string;
  summary: string;
  contents: Array<{ id: string; label: string }>;
  related: { label: string; to: "/privacy" | "/terms" };
  children: ReactNode;
}

export function LegalPage({
  title,
  updated,
  summary,
  contents,
  related,
  children,
}: LegalPageProps) {
  return (
    <>
      <div className="mx-auto max-w-6xl px-6 pb-24 pt-36 lg:px-8 lg:pb-32 lg:pt-44">
        <Link
          to="/"
          className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          Magnitai home
        </Link>

        <header className="mt-12 max-w-[50rem] border-b border-foreground pb-12">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Legal · Effective {updated}
          </p>
          <h1 className="mt-5 text-balance font-display text-[clamp(3.4rem,7vw,6.5rem)] font-normal leading-[0.9] tracking-[-0.055em]">
            {title}
          </h1>
          <p className="mt-7 max-w-[62ch] text-lg leading-8 text-muted-foreground">{summary}</p>
        </header>

        <div className="mt-12 grid gap-12 lg:grid-cols-[14rem_minmax(0,70ch)] lg:gap-16">
          <aside className="lg:sticky lg:top-32 lg:self-start">
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
              On this page
            </p>
            <nav className="mt-4 border-l border-border" aria-label={`${title} contents`}>
              {contents.map((item, index) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className="flex min-h-10 items-center gap-3 border-l border-transparent px-3 text-sm text-muted-foreground transition-colors hover:border-foreground hover:text-foreground"
                >
                  <span className="font-mono text-[9px] text-n-400">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {item.label}
                </a>
              ))}
            </nav>

            <Link
              to={related.to}
              className="group mt-8 inline-flex min-h-11 items-center gap-2 text-sm font-semibold"
            >
              {related.label}
              <ArrowRight
                className="size-3.5 transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </Link>
          </aside>

          <article className="legal-prose">{children}</article>
        </div>
      </div>

      <MarketingFooter />
    </>
  );
}
