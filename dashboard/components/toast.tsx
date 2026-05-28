"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

type ToastKind = "success" | "error" | "info";
interface ToastMsg {
  id: number;
  text: string;
  kind: ToastKind;
}

interface ToastCtx {
  push: (text: string, kind?: ToastKind) => void;
}

const Ctx = createContext<ToastCtx | null>(null);

export function useToast(): ToastCtx {
  const v = useContext(Ctx);
  if (!v) return { push: () => {} };
  return v;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastMsg[]>([]);

  const push = useCallback((text: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, text, kind }]);
  }, []);

  useEffect(() => {
    if (items.length === 0) return;
    const t = setTimeout(() => {
      setItems((prev) => prev.slice(1));
    }, 3200);
    return () => clearTimeout(t);
  }, [items]);

  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div className="toast-container">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
