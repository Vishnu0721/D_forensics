import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type LabelMode = "plain" | "formal";

type LabelContextValue = {
  mode: LabelMode;
  setMode: (m: LabelMode) => void;
  t: (plain: string, formal: string) => string;
};

const KEY = "df-label-mode";

const LabelContext = createContext<LabelContextValue | null>(null);

export function LabelModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<LabelMode>("plain");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(KEY);
      if (stored === "plain" || stored === "formal") setModeState(stored);
    } catch {
      /* ignore */
    }
  }, []);

  const setMode = (m: LabelMode) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* ignore */
    }
  };

  const value = useMemo(
    () => ({
      mode,
      setMode,
      t: (plain: string, formal: string) => (mode === "formal" ? formal : plain),
    }),
    [mode],
  );

  return <LabelContext.Provider value={value}>{children}</LabelContext.Provider>;
}

export function useLabels(): LabelContextValue {
  const ctx = useContext(LabelContext);
  if (!ctx) {
    return {
      mode: "plain",
      setMode: () => undefined,
      t: (plain) => plain,
    };
  }
  return ctx;
}
