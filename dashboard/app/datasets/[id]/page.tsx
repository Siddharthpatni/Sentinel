"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  type Dataset,
  type DatasetItem,
  deleteDatasetItem,
  fetchDataset,
  fetchDatasetItems,
} from "@/lib/api";

export default function DatasetDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [items, setItems] = useState<DatasetItem[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const [d, its] = await Promise.all([
        fetchDataset(id),
        fetchDatasetItems(id),
      ]);
      setDataset(d);
      setItems(its);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function remove(itemId: string) {
    if (!confirm("Remove this item?")) return;
    await deleteDatasetItem(id, itemId);
    await load();
  }

  if (err)
    return (
      <main className="flex-1 px-6 py-8 max-w-[1200px] w-full mx-auto">
        <p className="text-bad">{err}</p>
      </main>
    );

  return (
    <main className="flex-1 px-6 py-8 max-w-[1200px] w-full mx-auto">
      <Link
        href="/datasets"
        className="text-xs text-faint hover:text-fg"
      >
        ← All datasets
      </Link>
      <header className="mt-2 mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">
          {dataset?.name ?? "Loading…"}
        </h1>
        {dataset?.description && (
          <p className="text-sm text-muted mt-1">{dataset.description}</p>
        )}
        <p className="text-xs text-faint mt-2">
          {dataset?.item_count ?? 0} items · created{" "}
          {dataset && new Date(dataset.created_at).toLocaleDateString()}
        </p>
      </header>

      <div className="glass-panel overflow-hidden">
        {items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No items yet</div>
            <p className="empty-state-desc">
              Add items from the trace detail page (&ldquo;Add to
              dataset&rdquo;) or from the playground after a run.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-default">
            {items.map((it) => {
              const open = it.id === expandedId;
              const messages =
                (it.input as { messages?: unknown[] }).messages ?? [];
              const model =
                (it.input as { model?: string }).model ?? "(no model)";
              const firstUser =
                (messages as Array<{ role?: string; content?: string }>).find(
                  (m) => m.role === "user",
                )?.content ?? "";
              return (
                <li key={it.id} className="p-4">
                  <div className="flex items-start gap-3">
                    <button
                      type="button"
                      onClick={() => setExpandedId(open ? null : it.id)}
                      className="flex-1 text-left"
                    >
                      <div className="text-xs text-faint mb-1">
                        {model} ·{" "}
                        {new Date(it.created_at).toLocaleString()}
                        {it.source_trace_id && (
                          <>
                            {" · "}
                            <Link
                              href={`/traces/${it.source_trace_id}`}
                              className="text-accent hover:underline"
                              onClick={(e) => e.stopPropagation()}
                            >
                              source trace
                            </Link>
                          </>
                        )}
                      </div>
                      <div className="text-sm text-fg line-clamp-2">
                        {typeof firstUser === "string"
                          ? firstUser
                          : JSON.stringify(firstUser)}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => remove(it.id)}
                      className="text-xs text-faint hover:text-bad"
                    >
                      Delete
                    </button>
                  </div>
                  {open && (
                    <pre className="json-viewer text-xs mt-3">
                      {JSON.stringify(it, null, 2)}
                    </pre>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </main>
  );
}
