import { describe, it, expect, beforeEach } from "vitest";

describe("pipelineStore", () => {
  beforeEach(async () => {
    const { usePipelineStore } = await import("../stores/pipelineStore");
    usePipelineStore.setState({ messages: [], isRunning: false });
  });

  it("should have initial state", async () => {
    const { usePipelineStore } = await import("../stores/pipelineStore");
    const state = usePipelineStore.getState();
    expect(Array.isArray(state.messages)).toBe(true);
    expect(typeof state.isRunning).toBe("boolean");
  });

  it("should update running state", async () => {
    const { usePipelineStore } = await import("../stores/pipelineStore");
    usePipelineStore.getState().setRunning(true);
    expect(usePipelineStore.getState().isRunning).toBe(true);
  });

  it("should select a message", async () => {
    const { usePipelineStore } = await import("../stores/pipelineStore");
    usePipelineStore.getState().selectMessage("msg-123");
    expect(usePipelineStore.getState().selectedMessageId).toBe("msg-123");
  });

  it("should clear all messages", async () => {
    const { usePipelineStore } = await import("../stores/pipelineStore");
    usePipelineStore.getState().clearAllMessages();
    expect(usePipelineStore.getState().messages.length).toBe(0);
    expect(usePipelineStore.getState().selectedMessageId).toBeNull();
  });
});
