import { afterEach, describe, expect, test } from "bun:test";
import { apiGet } from "../src/helpers";

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

describe("Himalayas apiGet retry and error handling", () => {
  test("retries on 429 and succeeds on subsequent try", async () => {
    instantTimers();
    const state = stubFetch([
      () => new Response("rate limited", { status: 429 }),
      () => new Response(JSON.stringify({ jobs: [], limit: 20 }), { status: 200 }),
    ]);

    const res = await apiGet({ limit: 10, offset: 0 });
    expect(state.calls).toBe(2);
    expect(res.jobs).toEqual([]);
  });

  test("throws after exhausting retries on persistent 500", async () => {
    instantTimers();
    const state = stubFetch([() => new Response("server error", { status: 500 })]);

    await expect(apiGet({ limit: 10, offset: 0 })).rejects.toThrow(/request failed/i);
    expect(state.calls).toBe(7);
  });

  test("fails fast on network connection error without infinite retrying", async () => {
    const state = { calls: 0 };
    globalThis.fetch = (async () => {
      state.calls++;
      throw new Error("Connection refused");
    }) as unknown as typeof fetch;

    await expect(apiGet({ limit: 10, offset: 0 })).rejects.toThrow(/could not reach the Himalayas API/i);
    expect(state.calls).toBe(1);
  });
});
