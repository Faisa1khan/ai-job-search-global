import { afterEach, describe, expect, test } from "bun:test";
import { runSearch } from "../src/commands/search";
import { runDetail } from "../src/commands/detail";
import type { HimalayasJob, HimalayasResponse } from "../src/helpers";

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

function sampleJob(overrides: Partial<HimalayasJob> = {}): HimalayasJob {
  return {
    title: "Senior Frontend Engineer",
    excerpt: "Looking for a Senior Frontend Engineer to build web apps.",
    companyName: "Acme Corp",
    companySlug: "acme-corp",
    employmentType: "Full Time",
    minSalary: 120000,
    maxSalary: 150000,
    salaryPeriod: "annual",
    currency: "USD",
    seniority: ["Senior"],
    locationRestrictions: ["Worldwide"],
    categories: ["Developer", "Frontend-Development", "Software-Engineer"],
    description: "<p>We are hiring a <strong>Senior Frontend Engineer</strong>.</p>",
    pubDate: 1789380000,
    applicationLink: "https://himalayas.app/companies/acme-corp/jobs/senior-frontend-engineer-123456",
    guid: "https://himalayas.app/companies/acme-corp/jobs/senior-frontend-engineer-123456",
    ...overrides,
  };
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
  process.stderr.write = originalStderrWrite;
});

describe("Himalayas runSearch (mocked fetch)", () => {
  test("emits standard contract envelope { meta, results }", async () => {
    const mockData: HimalayasResponse = {
      jobs: [sampleJob()],
      limit: 20,
      offset: 0,
      totalCount: 1,
    };
    mockFetch(200, mockData);
    const out = captureStdout();

    const code = await runSearch({ page: 1, limit: 10, format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.meta).toEqual({ count: 1, page: 1 });
    expect(parsed.results).toHaveLength(1);
    expect(parsed.results[0].id).toBe("senior-frontend-engineer-123456");
    expect(parsed.results[0].site).toBe("himalayas");
    expect(parsed.results[0].title).toBe("Senior Frontend Engineer");
    expect(parsed.results[0].company).toBe("Acme Corp");
    expect(parsed.results[0].salary).toBe("USD 120,000–150,000 annual");
  });

  test("filters by keyword query", async () => {
    const mockData: HimalayasResponse = {
      jobs: [
        sampleJob({
          title: "Backend Engineer",
          excerpt: "Python API developer",
          applicationLink: "https://himalayas.app/companies/acme/jobs/backend-1",
        }),
        sampleJob({
          title: "Senior React Engineer",
          excerpt: "React developer",
          applicationLink: "https://himalayas.app/companies/acme/jobs/react-2",
        }),
      ],
    };
    mockFetch(200, mockData);
    const out = captureStdout();

    const code = await runSearch({ query: "React", page: 1, limit: 10, format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.results).toHaveLength(1);
    expect(parsed.results[0].title).toBe("Senior React Engineer");
  });

  test("handles network failure with SEARCH_FAILED", async () => {
    globalThis.fetch = (async () => {
      throw new Error("Network offline");
    }) as typeof fetch;
    const err = captureStderr();

    const code = await runSearch({ page: 1, limit: 10, format: "json" });
    expect(code).toBe(1);
    expect(JSON.parse(err.get()).code).toBe("SEARCH_FAILED");
  });
});

describe("Himalayas runDetail (mocked fetch)", () => {
  test("returns full job detail by slug", async () => {
    const mockData: HimalayasResponse = {
      jobs: [sampleJob()],
    };
    mockFetch(200, mockData);
    const out = captureStdout();

    const code = await runDetail({ id: "senior-frontend-engineer-123456", format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.id).toBe("senior-frontend-engineer-123456");
    expect(parsed.title).toBe("Senior Frontend Engineer");
    expect(parsed.fullDescription).toContain("Senior Frontend Engineer");
  });

  test("exits 1 with NOT_FOUND when job does not exist", async () => {
    mockFetch(200, { jobs: [] });
    const err = captureStderr();

    const code = await runDetail({ id: "non-existent-slug", format: "json" });
    expect(code).toBe(1);
    expect(JSON.parse(err.get()).code).toBe("NOT_FOUND");
  });
});
