import { afterEach, describe, expect, test } from "bun:test";
import { runSearch } from "../src/commands/search";
import { runDetail } from "../src/commands/detail";
import type { RemotiveJob, RemotiveResponse } from "../src/helpers";

const originalFetch = globalThis.fetch;
const originalStdoutWrite = process.stdout.write;
const originalStderrWrite = process.stderr.write;

function captureStdout(): { get: () => string } {
  let buf = "";
  process.stdout.write = ((chunk: string | Uint8Array) => {
    buf += chunk.toString();
    return true;
  }) as typeof process.stdout.write;
  return { get: () => buf };
}

function captureStderr(): { get: () => string } {
  let buf = "";
  process.stderr.write = ((chunk: string | Uint8Array) => {
    buf += chunk.toString();
    return true;
  }) as typeof process.stderr.write;
  return { get: () => buf };
}

function mockFetch(status: number, body: unknown): void {
  globalThis.fetch = (async () => {
    return new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
}

function sampleJob(overrides: Partial<RemotiveJob> = {}): RemotiveJob {
  return {
    id: 1001,
    url: "https://remotive.com/job/1001",
    title: "Senior Fullstack Engineer",
    company_name: "Tech Corp",
    category: "Software Development",
    tags: ["react", "typescript", "fullstack"],
    job_type: "full_time",
    publication_date: "2026-09-14T10:00:00",
    candidate_required_location: "Worldwide",
    salary: "$140,000 - $180,000",
    description: "<p>We are seeking a <strong>Senior Fullstack Engineer</strong>.</p>",
    ...overrides,
  };
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
  process.stderr.write = originalStderrWrite;
});

describe("Remotive runSearch (mocked fetch)", () => {
  test("emits standard contract envelope { meta, results }", async () => {
    const mockData: RemotiveResponse = {
      "job-count": 1,
      "total-job-count": 1,
      jobs: [sampleJob()],
    };
    mockFetch(200, mockData);
    const out = captureStdout();

    const code = await runSearch({ limit: 10, format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.meta.count).toBe(1);
    expect(parsed.results).toHaveLength(1);
    expect(parsed.results[0].id).toBe("1001");
    expect(parsed.results[0].site).toBe("remotive");
    expect(parsed.results[0].title).toBe("Senior Fullstack Engineer");
    expect(parsed.results[0].company).toBe("Tech Corp");
    expect(parsed.results[0].salary).toBe("$140,000 - $180,000");
  });

  test("filters by keyword and category", async () => {
    const mockData: RemotiveResponse = {
      jobs: [
        sampleJob({ id: 1001, title: "Product Manager", category: "Product" }),
        sampleJob({ id: 1002, title: "Frontend Developer", category: "Software Development" }),
      ],
    };
    mockFetch(200, mockData);
    const out = captureStdout();

    const code = await runSearch({ query: "Frontend", limit: 10, format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.results).toHaveLength(1);
    expect(parsed.results[0].title).toBe("Frontend Developer");
  });

  test("handles network failure with SEARCH_FAILED", async () => {
    globalThis.fetch = (async () => {
      throw new Error("Network offline");
    }) as typeof fetch;
    const err = captureStderr();

    const code = await runSearch({ limit: 10, format: "json" });
    expect(code).toBe(1);
    expect(JSON.parse(err.get()).code).toBe("SEARCH_FAILED");
  });
});

describe("Remotive runDetail (mocked fetch)", () => {
  test("returns full job detail by ID", async () => {
    const mockData: RemotiveResponse = {
      jobs: [sampleJob({ id: 1001 })],
    };
    mockFetch(200, mockData);
    const out = captureStdout();

    const code = await runDetail({ id: "1001", format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.id).toBe("1001");
    expect(parsed.title).toBe("Senior Fullstack Engineer");
    expect(parsed.fullDescription).toContain("Senior Fullstack Engineer");
  });

  test("exits 1 with NOT_FOUND when job does not exist", async () => {
    mockFetch(200, { jobs: [] });
    const err = captureStderr();

    const code = await runDetail({ id: "9999", format: "json" });
    expect(code).toBe(1);
    expect(JSON.parse(err.get()).code).toBe("NOT_FOUND");
  });
});
