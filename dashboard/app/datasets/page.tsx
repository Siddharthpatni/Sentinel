"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  type Dataset,
  createDataset,
  deleteDataset,
  fetchDatasets,
} from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Project {
  id: string;
  name: string;
}

export default function DatasetsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load(pid: string) {
    if (!pid) return;
    try {
      setDatasets(await fetchDatasets(pid));
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const pj = await fetch(`${API_URL}/api/projects`, {
          cache: "no-store",
        }).then((r) => r.json());
        setProjects(pj.projects);
        if (pj.projects.length > 0) {
          setProjectId(pj.projects[0].id);
          await load(pj.projects[0].id);
        }
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, []);

  async function submit() {
    if (!projectId || !name) return;
    setBusy(true);
    setErr(null);
    try {
      await createDataset({
        project_id: projectId,
        name,
        description: description || null,
      });
      setName("");
      setDescription("");
      await load(projectId);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete this dataset and all its items?")) return;
    await deleteDataset(id);
    await load(projectId);
  }

  return (
    <main className="flex-1 px-6 py-8 max-w-[1200px] w-full mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">
          Datasets
        </h1>
        <p className="text-sm text-muted">
          Named collections of input examples. Capture from traces, replay in
          the playground, target with eval suites.
        </p>
      </header>

      <div className="glass-panel p-5 mb-6">
        <h3 className="text-sm font-semibold text-fg mb-3">New dataset</h3>
        <div className="grid grid-cols-1 md:grid-cols-[200px_1fr_1fr_auto] gap-2">
          <select
            className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value);
              load(e.target.value);
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <input
            className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button
            type="button"
            className="btn-primary text-sm"
            disabled={busy || !name}
            onClick={submit}
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
        {err && <p className="text-bad text-xs mt-2">{err}</p>}
      </div>

      <div className="glass-panel overflow-hidden">
        {datasets.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No datasets yet</div>
            <p className="empty-state-desc">
              Create one above, or click &ldquo;Add to dataset&rdquo; on any
              trace.
            </p>
          </div>
        ) : (
          <table className="trace-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Items</th>
                <th>Description</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link
                      href={`/datasets/${d.id}`}
                      className="text-fg hover:text-accent"
                    >
                      {d.name}
                    </Link>
                  </td>
                  <td className="font-mono">{d.item_count}</td>
                  <td className="text-fg-soft">
                    {d.description || <span className="text-faint">—</span>}
                  </td>
                  <td className="text-faint">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => remove(d.id)}
                      className="text-xs text-faint hover:text-bad"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
