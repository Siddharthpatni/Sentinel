import Link from "next/link";

const links = [
  { href: "/", label: "Traces" },
  { href: "/verifications", label: "Verifications" },
  { href: "/policies", label: "Policies" },
  { href: "/evals", label: "Evals" },
];

export function NavBar() {
  return (
    <nav className="border-b border-neutral-800 bg-neutral-950 px-6 py-3">
      <div className="flex items-center gap-6">
        <span className="font-semibold text-neutral-100">Sentinel</span>
        <div className="flex items-center gap-4 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-neutral-400 hover:text-neutral-100 transition-colors"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
