/**
 * Shared motion constants and animation helpers.
 * Import from here instead of copy-pasting the ease curve or variant objects.
 */

/** The house cubic-bezier — snappy ease-out used by Vercel, Linear, and this product. */
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;

export const STAGGER_DELAY = 0.12;

/**
 * Framer-motion variant set for sequential reveal animations.
 * Use on a motion parent with `initial="hidden" animate="visible"`.
 */
export const reveal = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.65, ease: EASE_OUT },
  },
} as const;

/**
 * Parent variants for a staggered cascade of `reveal` children.
 * Use with `initial="hidden" animate="visible"` on the parent, and
 * `variants={reveal}` on each direct child.
 */
export const staggerContainer = {
  hidden: {},
  visible: {
    transition: { staggerChildren: STAGGER_DELAY },
  },
} as const;

/**
 * Framer-motion variant set for grid items that mount/unmount with
 * AnimatePresence (e.g. filtered card grids). Use with
 * `initial="hidden" animate="show" exit="hidden"`.
 */
export const itemAnimation = {
  hidden: { opacity: 0, y: 16, scale: 0.97 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.4, ease: EASE_OUT },
  },
} as const;

/**
 * Returns spread-ready framer-motion props for a whileInView fade-up.
 * @param delay - optional stagger delay in seconds
 */
export function fadeUp(delay = 0) {
  return {
    initial: { opacity: 0, y: 20 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, amount: 0.3 } as const,
    transition: { delay, duration: 0.5, ease: EASE_OUT },
  };
}

/**
 * Returns spread-ready framer-motion props for a horizontal slide-in.
 * @param direction - positive = from right, negative = from left
 * @param delay - optional stagger delay in seconds
 */
export function slideIn(direction: 1 | -1 = 1, delay = 0) {
  return {
    initial: { opacity: 0, x: direction * 16 },
    whileInView: { opacity: 1, x: 0 },
    viewport: { once: true, amount: 0.4 } as const,
    transition: { duration: 0.6, delay, ease: EASE_OUT },
  };
}
