import { useRef } from "react";
import type React from "react";

/**
 * Trap wheel scroll inside a scrollable container ONLY while it has more
 * content to reveal. Behaviour:
 *
 *   • If the container is not actually overflowing (scrollHeight ≈ clientHeight)
 *     we do nothing — the page (and Lenis) keep getting the wheel deltas, so
 *     the user can scroll past the block when records end inside it.
 *   • If it IS overflowing but we are at the top edge scrolling up, or at the
 *     bottom edge scrolling down, we let the page take over (no preventDefault,
 *     no stopPropagation).
 *   • Otherwise we stop propagation so the page doesn't double-scroll while
 *     we're consuming the delta inside the box.
 *
 * Shared by every block that previously froze the page when its content was
 * shorter than its max-height (Ranked shortlist, Schema mismatch, etc.).
 */
export function useScrollIsolation<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const onWheel = (e: React.WheelEvent<T>) => {
    const el = ref.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    const overflowing = scrollHeight - clientHeight > 1;
    if (!overflowing) return;
    const atTop = scrollTop <= 0;
    const atBottom = scrollTop + clientHeight >= scrollHeight - 1;
    if ((atTop && e.deltaY < 0) || (atBottom && e.deltaY > 0)) return;
    e.stopPropagation();
  };
  return { ref, onWheel };
}
