import { create } from "zustand";

export interface LogEntry {
  timestamp: number;
  level: string;
  logger: string;
  message: string;
  exc_info?: string;
}

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

interface LogStore {
  entries: LogEntry[];
  filterLevel: LogLevel | "ALL";
  autoScroll: boolean;
  maxEntries: number;

  addEntry: (entry: LogEntry) => void;
  setEntries: (entries: LogEntry[]) => void;
  setFilterLevel: (level: LogLevel | "ALL") => void;
  setAutoScroll: (v: boolean) => void;
  clear: () => void;
}

export const useLogStore = create<LogStore>((set) => ({
  entries: [],
  filterLevel: "ALL",
  autoScroll: true,
  maxEntries: 2000,

  addEntry: (entry) =>
    set((state) => ({
      entries: [...state.entries, entry].slice(-state.maxEntries),
    })),

  setEntries: (entries) => set({ entries }),

  setFilterLevel: (level) => set({ filterLevel: level }),

  setAutoScroll: (v) => set({ autoScroll: v }),

  clear: () => set({ entries: [] }),
}));
