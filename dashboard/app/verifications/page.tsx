interface Rule {
  id: string;
  name: string;
  match_jsonpath: string;
  sample_rate: number;
  judge_model: string;
  enabled: boolean;
}

interface RuleList {
  rules: Rule[];
  total: number;
}

async function fetchRules(): Promise<RuleList> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${apiUrl}/api/verification-rules`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch rules: ${res.status}`);
  return res.json();
}

export default async function VerificationsPage() {
  let data: RuleList = { rules: [], total: 0 };
  let error: string | null = null;
  try {
    data = await fetchRules();
  } catch (e) {
    error = e instanceof Error ? e.message : "unknown error";
  }

  return (
    <main className="p-6 text-neutral-100">
      <h1 className="text-2xl font-semibold mb-1">Verifications</h1>
      <p className="text-neutral-400 mb-6 text-sm">
        Judge-model evaluations of primary calls. Phase 2 — Step 2 of 15.
      </p>

      <section className="mb-8">
        <h2 className="text-lg font-medium mb-2">Verification rules ({data.total})</h2>
        {error && (
          <div className="rounded border border-red-800 bg-red-950/40 p-3 text-sm text-red-300">
            Could not reach gateway: {error}
          </div>
        )}
        {!error && data.rules.length === 0 && (
          <div className="rounded border border-neutral-800 bg-neutral-950 p-4 text-sm text-neutral-400">
            No rules yet. POST one to <code>/api/verification-rules</code> to get started.
          </div>
        )}
        {!error && data.rules.length > 0 && (
          <table className="w-full text-sm border border-neutral-800 rounded">
            <thead className="bg-neutral-900 text-neutral-400 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Judge model</th>
                <th className="px-3 py-2">Sample rate</th>
                <th className="px-3 py-2">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {data.rules.map((r) => (
                <tr key={r.id} className="border-t border-neutral-800">
                  <td className="px-3 py-2 font-mono">{r.name}</td>
                  <td className="px-3 py-2">{r.judge_model}</td>
                  <td className="px-3 py-2">{r.sample_rate}</td>
                  <td className="px-3 py-2">
                    <span
                      className={
                        r.enabled
                          ? "rounded bg-emerald-900/40 px-2 py-0.5 text-emerald-300"
                          : "rounded bg-neutral-800 px-2 py-0.5 text-neutral-400"
                      }
                    >
                      {r.enabled ? "on" : "off"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">Verifications feed</h2>
        <div className="rounded border border-neutral-800 bg-neutral-950 p-4 text-sm text-neutral-500">
          Coming in Step 5 (<code>/api/verifications</code> endpoint).
        </div>
      </section>
    </main>
  );
}
