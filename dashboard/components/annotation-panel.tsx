"use client";

import { useCallback, useEffect, useState } from "react";
import {
  type Annotation,
  createAnnotation,
  deleteAnnotation,
  fetchAnnotations,
} from "@/lib/api";

const RATINGS: { value: Annotation["rating"]; label: string; emoji: string }[] = [
  { value: "thumbs_up", label: "Thumbs up", emoji: "👍" },
  { value: "thumbs_down", label: "Thumbs down", emoji: "👎" },
  { value: "neutral", label: "Neutral", emoji: "○" },
];

export function AnnotationPanel({ traceId }: { traceId: string }) {
  const [rows, setRows] = useState<Annotation[]>([]);
  const [rating, setRating] = useState<Annotation["rating"]>("thumbs_up");
  const [dimension, setDimension] = useState("overall");
  const [comment, setComment] = useState("");
  const [author, setAuthor] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setRows(await fetchAnnotations(traceId));
    } catch (e) {
      setErr(String(e));
    }
  }, [traceId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const submit = async () => {
    setSubmitting(true);
    setErr(null);
    try {
      await createAnnotation({
        trace_id: traceId,
        rating,
        dimension: dimension || "overall",
        comment: comment || null,
        author: author || null,
      });
      setComment("");
      await reload();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id: string) => {
    await deleteAnnotation(id);
    await reload();
  };

  return (
    <div className="glass-panel p-5">
      <h3
        className="text-sm font-semibold mb-4"
        style={{ color: "var(--sentinel-text-primary)" }}
      >
        Human Feedback
      </h3>

      <div className="flex flex-wrap gap-2 mb-3">
        {RATINGS.map((r) => (
          <button
            key={r.value}
            type="button"
            onClick={() => setRating(r.value)}
            className={
              "px-3 py-1.5 rounded text-sm border transition " +
              (rating === r.value
                ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-200"
                : "bg-neutral-900 border-neutral-700 text-neutral-300 hover:border-neutral-500")
            }
          >
            {r.emoji} {r.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-2">
        <input
          className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm text-neutral-100"
          placeholder="Dimension (e.g. overall, accuracy)"
          value={dimension}
          onChange={(e) => setDimension(e.target.value)}
        />
        <input
          className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm text-neutral-100"
          placeholder="Your name (optional)"
          value={author}
          onChange={(e) => setAuthor(e.target.value)}
        />
      </div>
      <textarea
        className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm text-neutral-100 mb-2"
        placeholder="Comment (optional)"
        rows={2}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <button
        type="button"
        className="btn-primary text-sm"
        disabled={submitting}
        onClick={submit}
      >
        {submitting ? "Submitting…" : "Submit feedback"}
      </button>
      {err && <p className="text-red-400 text-xs mt-2">{err}</p>}

      {rows.length > 0 && (
        <ul className="mt-5 space-y-2 border-t border-neutral-800 pt-3">
          {rows.map((a) => (
            <li
              key={a.id}
              className="flex items-start gap-3 text-sm border border-neutral-800 rounded p-2"
            >
              <span className="text-lg leading-none">
                {a.rating === "thumbs_up"
                  ? "👍"
                  : a.rating === "thumbs_down"
                    ? "👎"
                    : "○"}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-neutral-500">
                  <span className="text-neutral-300">{a.author || "anon"}</span>
                  {" · "}
                  <span>{a.dimension}</span>
                  {" · "}
                  <span>{new Date(a.created_at).toLocaleString()}</span>
                </div>
                {a.comment && (
                  <div className="text-neutral-200 mt-0.5 break-words">
                    {a.comment}
                  </div>
                )}
              </div>
              <button
                type="button"
                className="text-xs text-neutral-500 hover:text-red-400"
                onClick={() => remove(a.id)}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
