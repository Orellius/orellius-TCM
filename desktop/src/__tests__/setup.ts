// Vitest setup file — mocks for Tauri APIs that don't exist in jsdom
import { vi } from "vitest";

// Mock @tauri-apps/api
vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(() => Promise.resolve(() => {})),
  emit: vi.fn(),
}));

// Mock fetch globally
(globalThis as Record<string, unknown>).fetch = vi.fn();
