import { afterEach, describe, expect, test } from "bun:test";
import { runSearch } from "../src/commands/search";
import { runDetail } from "../src/commands/detail";

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

function mockFetchRouter(routes: Record<string, unknown>): void {
  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    for (const [pattern, body] of Object.entries(routes)) {
      if (url.includes(pattern)) {
        return new Response(typeof body === "string" ? body : JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
    }
    return new Response("Not found", { status: 404 });
  }) as typeof fetch;
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
  process.stderr.write = originalStderrWrite;
});

describe("ATS runSearch (mocked fetch)", () => {
  test("emits standard contract envelope across providers", async () => {
    mockFetchRouter({
      "greenhouse.io/v1/boards/vercel/jobs": {
        jobs: [
          {
            id: 991,
            title: "Senior Frontend Engineer",
            absolute_url: "https://boards.greenhouse.io/vercel/jobs/991",
            location: { name: "Remote" },
            content: "We are hiring a Senior Frontend Engineer",
            updated_at: "2026-09-14T00:00:00Z",
          },
        ],
      },
      "api.ashbyhq.com/posting-api/job-board/notion": {
        jobs: [
          {
            id: "notion-1",
            title: "Product Engineer (React)",
            jobUrl: "https://jobs.ashbyhq.com/notion/notion-1",
            location: "Remote",
            publishedAt: "2026-09-14T00:00:00Z",
            descriptionPlain: "Build with React and TypeScript",
          },
        ],
      },
      "api.lever.co/v0/postings/meesho": [
        {
          id: "meesho-1",
          text: "Senior Software Engineer",
          hostedUrl: "https://jobs.lever.co/meesho/meesho-1",
          categories: { location: "Bangalore" },
          createdAt: 1789380000000,
          descriptionPlain: "Fullstack engineering role",
        },
      ],
    });

    const out = captureStdout();
    const code = await runSearch({ limit: 10, format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.meta.count).toBeGreaterThanOrEqual(1);
    expect(parsed.results.length).toBeGreaterThanOrEqual(1);

    const first = parsed.results[0];
    expect(first).toHaveProperty("id");
    expect(first).toHaveProperty("site");
    expect(first).toHaveProperty("title");
    expect(first).toHaveProperty("company");
    expect(first).toHaveProperty("location");
    expect(first).toHaveProperty("url");
  });

  test("filters by keyword query", async () => {
    mockFetchRouter({
      "greenhouse.io/v1/boards/vercel/jobs": {
        jobs: [
          {
            id: 991,
            title: "Senior React Developer",
            absolute_url: "https://boards.greenhouse.io/vercel/jobs/991",
            location: { name: "Remote" },
            content: "React Next.js TypeScript",
          },
          {
            id: 992,
            title: "Account Executive",
            absolute_url: "https://boards.greenhouse.io/vercel/jobs/992",
            location: { name: "Remote" },
            content: "Enterprise sales",
          },
        ],
      },
    });

    const out = captureStdout();
    const code = await runSearch({ query: "React", company: "vercel", limit: 10, format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.results).toHaveLength(1);
    expect(parsed.results[0].title).toBe("Senior React Developer");
  });
});

describe("ATS runDetail (mocked fetch)", () => {
  test("returns Greenhouse job detail by composite ID", async () => {
    mockFetchRouter({
      "greenhouse.io/v1/boards/vercel/jobs/991": {
        id: 991,
        title: "Senior Frontend Engineer",
        absolute_url: "https://boards.greenhouse.io/vercel/jobs/991",
        content: "<p>Detailed description</p>",
      },
    });

    const out = captureStdout();
    const code = await runDetail({ id: "greenhouse:vercel:991", format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.id).toBe("greenhouse:vercel:991");
    expect(parsed.title).toBe("Senior Frontend Engineer");
    expect(parsed.description).toBe("Detailed description");
  });

  test("returns Ashby job detail by direct URL", async () => {
    mockFetchRouter({
      "api.ashbyhq.com/posting-api/job-board/notion": {
        jobs: [
          {
            id: "notion-1",
            title: "Product Engineer",
            jobUrl: "https://jobs.ashbyhq.com/notion/notion-1",
            descriptionPlain: "Build great products",
          },
        ],
      },
    });

    const out = captureStdout();
    const code = await runDetail({ id: "https://jobs.ashbyhq.com/notion/notion-1", format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.id).toBe("ashby:notion:notion-1");
    expect(parsed.title).toBe("Product Engineer");
  });

  test("returns Lever job detail by direct URL", async () => {
    mockFetchRouter({
      "api.lever.co/v0/postings/meesho/meesho-1": {
        id: "meesho-1",
        text: "Staff Engineer",
        hostedUrl: "https://jobs.lever.co/meesho/meesho-1",
        descriptionPlain: "Lead architecture",
      },
    });

    const out = captureStdout();
    const code = await runDetail({ id: "https://jobs.lever.co/meesho/meesho-1", format: "json" });
    expect(code).toBe(0);

    const parsed = JSON.parse(out.get());
    expect(parsed.id).toBe("lever:meesho:meesho-1");
    expect(parsed.title).toBe("Staff Engineer");
  });

  test("exits 1 with NOT_FOUND when job does not exist", async () => {
    mockFetchRouter({});
    const err = captureStderr();

    const code = await runDetail({ id: "greenhouse:vercel:404", format: "json" });
    expect(code).toBe(1);
    expect(JSON.parse(err.get()).code).toBe("NOT_FOUND");
  });
});
