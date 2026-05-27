"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Traces" },
  { href: "/sessions", label: "Sessions" },
  { href: "/verifications", label: "Verifications" },
  { href: "/policies", label: "Policies" },
  { href: "/evals", label: "Evals" },
  { href: "/audit", label: "Audit" },
  { href: "/alerts", label: "Alerts" },
];

export function NavBar() {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav className="sticky top-0 z-10 border-b border-neutral-800 bg-neutral-950/90 px-6 py-3 backdrop-blur">
      <div className="flex items-center gap-8">
        <Link href="/" className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-400" />
          <span className="font-semibold tracking-tight text-neutral-100">
            Sentinel
          </span>
        </Link>
        <div className="flex items-center gap-1 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={
                "rounded px-3 py-1.5 transition-colors " +
                (isActive(l.href)
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100")
              }
            >
              {l.label}
            </Link>
          ))}
        </div>
        <span className="ml-auto text-xs text-neutral-500">
          Phase 3 — compliance · alerting · charts
        </span>
      </div>
    </nav>
  );
}
