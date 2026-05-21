import { create } from "zustand";

export type ToastType = "error" | "success" | "info";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  /** Auto-dismiss timeout in ms (default 4000) */
  duration: number;
}

interface ToastStore {
  toasts: Toast[];
  addToast: (message: string, type?: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
}

let _nextId = 0;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],

  addToast: (message, type = "error", duration = 4000) => {
    const id = String(++_nextId);
    set((state) => ({
      toasts: [...state.toasts, { id, message, type, duration }],
    }));
    // Auto-dismiss
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, duration);
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));

/** Shorthand helpers */
export const toast = {
  error: (msg: string, duration?: number) =>
    useToastStore.getState().addToast(msg, "error", duration),
  success: (msg: string, duration?: number) =>
    useToastStore.getState().addToast(msg, "success", duration ?? 3000),
  info: (msg: string, duration?: number) =>
    useToastStore.getState().addToast(msg, "info", duration ?? 3000),
};
