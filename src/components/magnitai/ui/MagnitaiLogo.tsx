import React from "react";

interface MagnitaiLogoProps {
  /** "sm" = size-7 (footer), "md" = size-9 (nav). Defaults to "md". */
  size?: "sm" | "md";
  /** Show wordmark "magnitai" next to the logo image. Defaults to true. */
  showWordmark?: boolean;
  /** Extra classes on the root flex container */
  className?: string;
}

/**
 * Magnitai logo mark + wordmark lockup.
 * Replaces the copy-paste in Navigation.tsx and LandingPage footer.
 * Also pins the hardcoded bg-[#f8f3ec] to one place.
 */
export function MagnitaiLogo({ size = "md", showWordmark = true, className }: MagnitaiLogoProps) {
  const imgSize = size === "sm" ? "size-7 rounded-lg" : "size-9 rounded-[11px] shadow-sm";

  return (
    <div className={`flex items-center gap-2 ${className ?? ""}`}>
      <span
        className={`grid ${imgSize} place-items-center overflow-hidden bg-[#f8f3ec] ring-1 ring-black/5`}
      >
        <img
          src="/new-logo.jpg?v=3"
          alt="Magnitai logo"
          className="size-full scale-[1.5] object-cover"
        />
      </span>
      {showWordmark && (
        <span className="font-heading text-lg font-bold tracking-[-0.04em]">magnitai</span>
      )}
    </div>
  );
}
