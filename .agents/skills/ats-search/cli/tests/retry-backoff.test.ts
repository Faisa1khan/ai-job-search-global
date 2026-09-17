import { afterEach, describe, expect, test } from "bun:test";
import { fetchWithBackoff } from "../src/helpers";

const originalFetch = globalThis.fetch;
const originalSetTimeout = globalThis.setTimeout;

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.setTimeout = originalSetTimeout;
});

function instantTimers() {
  globalThis.setTimeout = ((fn: () => void) =>
    originalSetTimeout(fn, 0)) as unknown as typeof setTimeout;
}

function stubFetch(responses: Array<() => Response>): { calls: number } {
  const state = { calls: 0 };
  globalThis.fetch = (async () => {
    const i = Math.min(state.calls, responses.length - 1);
    state.calls++;
    return responses[i]();
  }) as unknown as typeof fetch;
  return state;
}

describe("ATS fetchWithBackoff retry and error handling", () => {
  test("retries on 429 and succeeds on subsequent try", async () => {
    instantTimers();
    const state = stubFetch([
      () => new Response("rate limited", { status: 429 }),
      () => new Response(JSON.stringify({ jobs: [] }), { status: 200 }),
    ]);

    const res = await fetchWithBackoff("https://example.com/api");
    expect(state.calls).toBe(2);
    expect(res).toEqual({ jobs: [] });
  });

  test("returns null on 404 without retrying", async () => {
    const state = stubFetch([() => new Response("Not found", { status: 404 })]);

    const res = await fetchWithBackoff("https://example.com/api");
    expect(res).toBeNull();
    expect(state.calls).toBe(1);
  });

  test("throws after exhausting retries on persistent 500", async () => {
    instantTimers();
    const state = stubFetch([() => new Response("server error", { status: 500 })]);

    await expect(fetchWithBackoff("https://example.com/api")).rejects.toThrow(/request failed/i);
    expect(state.calls).toBe(7);
  });

  test("fails fast on network connection error without infinite retrying", async () => {
    const state = { calls: 0 };
    globalThis.fetch = (async () => {
      state.calls++;
      throw new Error("Connection refused");
    }) as unknown as typeof fetch;

    await expect(fetchWithBackoff("https://example.com/api")).rejects.toThrow(/Connection error/i);
    expect(state.calls).toBe(1);
  });
});
