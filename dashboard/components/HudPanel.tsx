"use client";

import type { ReactNode } from "react";

/* ================================================================
   HudPanel — shared tactical-frame wrapper (corner brackets) used
   across the Control Room, incident list, and ops-center shell so
   the "HUD" chrome is defined once instead of copy-pasted per panel.
   ================================================================ */

export function HudPanel({
  title,
  elevated = false,
  padded = true,
  className = "",
  children,
}: {
  title?: string;
  elevated?: boolean;
  /** Set false when children manage their own padding (e.g. a flush-edge diff viewer). */
  padded?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`hud-frame ${elevated ? "glass-panel-elevated" : "glass-panel"} ${padded ? "p-5" : ""} ${className}`}
    >
      <span className="hud-corner hud-corner-tl" />
      <span className="hud-corner hud-corner-tr" />
      <span className="hud-corner hud-corner-bl" />
      <span className="hud-corner hud-corner-br" />
      {title && <div className={`hud-title ${padded ? "mb-4" : "p-3 border-b border-subtle"}`}>{title}</div>}
      {children}
    </div>
  );
}
