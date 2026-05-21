import { invoke } from "@tauri-apps/api/core";

/**
 * Typed wrapper around Tauri's invoke() for calling Rust commands.
 * Usage: const result = await tauriCommand<StatusResponse>("get_status");
 */
export async function tauriCommand<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  return invoke<T>(cmd, args);
}
