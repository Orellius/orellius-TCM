import { describe, it, expect, vi, beforeEach } from "vitest";

describe("API client", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok" }),
    });
  });

  it("should make requests without auth header when no token", async () => {
    const { api } = await import("../lib/api");
    await api.health();

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [, options] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers["Authorization"]).toBeUndefined();
  });

  it("should include auth header when token is set", async () => {
    localStorage.setItem("orellius_api_token", "my-secret");

    vi.resetModules();
    const { api } = await import("../lib/api");
    await api.health();

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [, options] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(options.headers["Authorization"]).toBe("Bearer my-secret");
  });
});
