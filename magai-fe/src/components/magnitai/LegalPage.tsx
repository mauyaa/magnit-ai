import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

interface LegalPageProps {
  title: string;
  updated: string;
  children: ReactNode;
}

export function LegalPage({ title, updated, children }: LegalPageProps) {
  return (
    <article className="mx-auto min-h-screen max-w-3xl px-6 pb-24 pt-32 sm:pt-40">
      <Link
        to="/"
        className="inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <ArrowLeft className="size-4" /> Back to Magnitai
      </Link>
      <p className="eyebrow mt-12">Legal</p>
      <h1 className="mt-4 font-heading text-5xl font-medium tracking-[-0.045em] sm:text-6xl">
        {title}
      </h1>
      <p className="mt-4 text-sm font-medium text-muted-foreground">Last updated {updated}</p>
      <div className="mt-12 space-y-8 text-base font-medium leading-8 text-muted-foreground [&_h2]:font-heading [&_h2]:text-2xl [&_h2]:font-semibold [&_h2]:text-foreground">
        {children}
      </div>
    </article>
  );
}
