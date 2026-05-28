"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  type Dataset,
  type Trace,
  addDatasetItem,
  fetchDatasets,
} from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Project {
  id: string;
  name: string;
}

export function TraceActions({ trace }: { trace: Trace }) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [saveTo, setSaveTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const pj = await fetch(`${API_URL}/api/projects`, {
          cache: "no-store",
        }).then((r) => r.json());
        setProjects(pj.projects);
        const owning = (pj.projects as Project[]).find(
          (p) => p.id === trace.project_id,
        );
        if (owning) setDatasets(await fetchDatasets(owning.id));
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, [trace.project_id]);

  function replay() {
    const messages =
      (trace.request_body as { messages?: unknown[] } | null)?.messages ?? [];
    const model =
      (trace.request_body as { model?: string } | null)?.model ?? trace.model;
    try {
      sessionStorage.setItem(
        "sentinel-playground-prefill",
        JSON.stringify({ model, messages, project_id: trace.project_id }),
      );
    } catch {
      /* ignore */
    }
    router.push("/playground");
  }

  async function save() {
    if (!saveTo) return;
    setBusy(true);
    setErr(null);
    try {
      await addDatasetItem(saveTo, {
        input: trace.request_body ?? {},
        expected_output: trace.response_body ?? null,
        source_trace_id: trace.id,
      });
      setPickerOpen(false);
      alert("Saved to dataset");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const owningProject = projects.find((p) => p.id === trace.project_id);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="btn-ghost text-sm" onClick={replay}>
        ↻ Replay in playground
      </button>
      <button
        type="button"
        className="btn-ghost text-sm"
        onClick={() => setPickerOpen((v) => !v)}
      >
        + Add to dataset
      </button>
      {owningProject && (
        <span className="text-xs text-faint">
          project: {owningProject.name}
        </span>
      )}
      {pickerOpen && (
        <div className="w-full glass-panel p-3 mt-2 grid grid-cols-[1fr_auto_auto] gap-2 items-center">
          <select
            className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
            value={saveTo}
            onChange={(e) => setSaveTo(e.target.value)}
          >
            <option value="">— pick dataset —</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.item_count})
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn-primary text-sm"
            onClick={save}
            disabled={busy || !saveTo}
          >
            {busy ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            className="text-xs text-faint hover:text-fg"
            onClick={() => setPickerOpen(false)}
          >
            Cancel
          </button>
          {err && (
            <p className="col-span-3 text-bad text-xs">{err}</p>
          )}
        </div>
      )}
    </div>
  );
}
