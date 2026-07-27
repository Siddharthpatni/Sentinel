"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./theme-toggle";

const links = [
  { href: "/", label: "Traces" },
  { href: "/sessions", label: "Sessions" },
  { href: "/playground", label: "Playground" },
  { href: "/verifications", label: "Verifications" },
  { href: "/policies", label: "Policies" },
  { href: "/evals", label: "Evals" },
  { href: "/datasets", label: "Datasets" },
  { href: "/audit", label: "Audit" },
  { href: "/incidents", label: "Incidents" },
  { href: "/annotations", label: "Queue" },
  { href: "/alerts", label: "Alerts" },
  { href: "/settings/keys", label: "Keys" },
];

export function NavBar() {
  const pathname = usePathname();

  // /incident-panel renders its own full-viewport shell (sidebar + top
  // bar), so it opts out of the global horizontal nav rather than stacking
  // two navigation bars.
  if (pathname?.startsWith("/incident-panel")) return null;

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav className="sticky top-0 z-10 border-b border-subtle bg-surface/85 px-6 py-3 backdrop-blur">
      <div className="flex items-center gap-8">
        <Link href="/" className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-accent shadow-[0_0_8px_var(--sentinel-accent-glow)]" />
          <span className="font-semibold tracking-tight text-fg">
            Sentinel
          </span>
        </Link>
        <div className="flex items-center gap-1 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={
                "rounded-md px-3 py-1.5 transition-colors " +
                (isActive(l.href)
                  ? "bg-accent-soft text-fg shadow-[inset_0_-2px_0_var(--sentinel-accent)]"
                  : "text-muted hover:bg-surface-1 hover:text-fg")
              }
            >
              {l.label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden text-xs text-faint md:inline">
            Phase 3 — observability · routing · BYOK
          </span>
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
