"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type Dataset,
  addDatasetItem,
  createDataset,
  fetchDatasets,
} from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Project {
  id: string;
  name: string;
  api_key: string;
}

interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

const COMMON_MODELS = [
  "gpt-4o-mini",
  "gpt-4o",
  "claude-3-5-sonnet-20241022",
  "openrouter/anthropic/claude-3-haiku",
];

export default function PlaygroundPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [model, setModel] = useState("gpt-4o-mini");
  const [messages, setMessages] = useState<Message[]>([
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "" },
  ]);
  const [response, setResponse] = useState<string | null>(null);
  const [meta, setMeta] = useState<{
    latency_ms: number;
    prompt_tokens?: number;
    completion_tokens?: number;
    trace_id?: string;
  } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [saveTo, setSaveTo] = useState("");
  const [newDsName, setNewDsName] = useState("");

  const project = useMemo(
    () => projects.find((p) => p.id === projectId),
    [projects, projectId],
  );

  useEffect(() => {
    (async () => {
      try {
        const pj = await fetch(`${API_URL}/api/projects`, {
          cache: "no-store",
        }).then((r) => r.json());
        setProjects(pj.projects);
        if (pj.projects.length > 0) {
          setProjectId(pj.projects[0].id);
          setDatasets(await fetchDatasets(pj.projects[0].id));
        }
      } catch (e) {
        setErr(String(e));
      }
    })();
  }, []);

  async function onProjectChange(pid: string) {
    setProjectId(pid);
    try {
      setDatasets(await fetchDatasets(pid));
    } catch {
      setDatasets([]);
    }
  }

  function updateMessage(i: number, patch: Partial<Message>) {
    setMessages((ms) => ms.map((m, idx) => (idx === i ? { ...m, ...patch } : m)));
  }
  function addMessage() {
    setMessages((ms) => [...ms, { role: "user", content: "" }]);
  }
  function removeMessage(i: number) {
    setMessages((ms) => ms.filter((_, idx) => idx !== i));
  }

  async function run() {
    if (!project) return;
    setRunning(true);
    setErr(null);
    setResponse(null);
    setMeta(null);
    const started = performance.now();
    try {
      const r = await fetch(`${API_URL}/v1/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${project.api_key}`,
        },
        body: JSON.stringify({
          model,
          messages: messages.filter((m) => m.content.trim().length > 0),
        }),
      });
      const elapsed = Math.round(performance.now() - started);
      const text = await r.text();
      if (!r.ok) {
        setErr(`${r.status}: ${text}`);
        return;
      }
      const body = JSON.parse(text);
      const content: string =
        body.choices?.[0]?.message?.content ?? JSON.stringify(body);
      setResponse(content);
      setMeta({
        latency_ms: elapsed,
        prompt_tokens: body.usage?.prompt_tokens,
        completion_tokens: body.usage?.completion_tokens,
        trace_id: body.id,
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  }

  async function saveToDataset() {
    if (!projectId) return;
    setErr(null);
    try {
      let dsId = saveTo;
      if (!dsId && newDsName) {
        const created = await createDataset({
          project_id: projectId,
          name: newDsName,
        });
        dsId = created.id;
        setDatasets(await fetchDatasets(projectId));
        setSaveTo(dsId);
        setNewDsName("");
      }
      if (!dsId) {
        setErr("Pick a dataset or enter a new name");
        return;
      }
      await addDatasetItem(dsId, {
        input: {
          model,
          messages: messages.filter((m) => m.content.trim().length > 0),
        },
        expected_output: response ? { content: response } : null,
      });
      alert("Saved to dataset");
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <main className="flex-1 px-6 py-8 max-w-[1200px] w-full mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-fg">
          Playground
        </h1>
        <p className="text-sm text-muted">
          Run prompts through Sentinel and save promising runs to a dataset
          for evals or regression testing.
        </p>
      </header>

      <div className="glass-panel p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-faint uppercase tracking-wide">
              Project
            </span>
            <select
              className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
              value={projectId}
              onChange={(e) => onProjectChange(e.target.value)}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-faint uppercase tracking-wide">
              Model
            </span>
            <input
              list="model-options"
              className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
            <datalist id="model-options">
              {COMMON_MODELS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </label>
          <button
            type="button"
            className="btn-primary text-sm"
            disabled={running || !project}
            onClick={run}
          >
            {running ? "Running…" : "Run"}
          </button>
        </div>
      </div>

      <div className="glass-panel p-5 mb-6">
        <h3 className="text-sm font-semibold text-fg mb-3">Messages</h3>
        <div className="space-y-2">
          {messages.map((m, i) => (
            <div key={i} className="grid grid-cols-[120px_1fr_auto] gap-2">
              <select
                className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
                value={m.role}
                onChange={(e) =>
                  updateMessage(i, { role: e.target.value as Message["role"] })
                }
              >
                <option value="system">system</option>
                <option value="user">user</option>
                <option value="assistant">assistant</option>
              </select>
              <textarea
                className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
                rows={Math.max(2, Math.min(8, m.content.split("\n").length))}
                value={m.content}
                onChange={(e) => updateMessage(i, { content: e.target.value })}
              />
              <button
                type="button"
                className="text-xs text-faint hover:text-bad self-start mt-1"
                onClick={() => removeMessage(i)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="btn-ghost text-sm mt-3"
          onClick={addMessage}
        >
          + Add message
        </button>
      </div>

      {err && (
        <div className="glass-panel p-4 mb-6 border border-bad">
          <p className="text-bad text-sm font-mono break-all">{err}</p>
        </div>
      )}

      {response !== null && (
        <div className="glass-panel p-5 mb-6">
          <div className="flex items-baseline justify-between mb-3">
            <h3 className="text-sm font-semibold text-fg">Response</h3>
            {meta && (
              <div className="text-xs text-faint">
                {meta.latency_ms}ms
                {meta.prompt_tokens !== undefined && (
                  <>
                    {" · "}
                    {meta.prompt_tokens}+{meta.completion_tokens} tokens
                  </>
                )}
              </div>
            )}
          </div>
          <pre className="json-viewer text-sm whitespace-pre-wrap">
            {response}
          </pre>

          <div className="mt-4 border-t border-default pt-3">
            <h4 className="text-xs text-faint uppercase tracking-wide mb-2">
              Save to dataset
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-2">
              <select
                className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
                value={saveTo}
                onChange={(e) => setSaveTo(e.target.value)}
              >
                <option value="">— existing dataset —</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.item_count})
                  </option>
                ))}
              </select>
              <input
                className="bg-surface border border-default rounded px-2 py-1.5 text-sm text-fg"
                placeholder="or new dataset name"
                value={newDsName}
                onChange={(e) => setNewDsName(e.target.value)}
                disabled={!!saveTo}
              />
              <button
                type="button"
                className="btn-primary text-sm"
                onClick={saveToDataset}
                disabled={!saveTo && !newDsName}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
