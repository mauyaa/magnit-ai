export const MARK_ASPECT = 100 / 71.45;

export function MagnitaiMark({ className }: { className?: string; mono?: boolean }) {
  return (
    <img
      src="/magnit-logo-cropped.png"
      alt=""
      aria-hidden="true"
      className={`block object-contain ${className ?? ""}`}
    />
  );
}

interface MagnitaiLogoProps {
  size?: "sm" | "md";
  showWordmark?: boolean;
  variant?: "tile" | "plain";
  className?: string;
}

/** Uses the supplied Magnit artwork without redrawing or recolouring the mark. */
export function MagnitaiLogo({
  size = "md",
  showWordmark = true,
  variant = "tile",
  className,
}: MagnitaiLogoProps) {
  const box = size === "sm" ? "h-7 w-9" : "h-9 w-11";
  return (
    <div className={`flex items-center gap-2.5 ${className ?? ""}`}>
      <span
        className={`grid shrink-0 place-items-center ${
          variant === "tile" ? "rounded-[10px] bg-white px-0.5" : ""
        }`}
      >
        <MagnitaiMark className={box} />
      </span>
      {showWordmark && <span className="text-lg font-semibold tracking-[-0.03em]">magnitai</span>}
    </div>
  );
}
