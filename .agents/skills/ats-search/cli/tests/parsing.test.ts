import { describe, expect, test } from "bun:test";
import { parseIdentifier } from "../src/commands/detail";
import { cleanHtml, decodeHtmlEntities, loadWatchlist } from "../src/helpers";

describe("ATS Watchlist parsing and identifiers", () => {
  test("parseIdentifier parses composite ID", () => {
    const gh = parseIdentifier("greenhouse:stripe:12345");
    expect(gh).toEqual({ provider: "greenhouse", slug: "stripe", jobId: "12345" });

    const lv = parseIdentifier("lever:meesho:abcd-1234");
    expect(lv).toEqual({ provider: "lever", slug: "meesho", jobId: "abcd-1234" });

    const as = parseIdentifier("ashby:notion:uuid-xyz");
    expect(as).toEqual({ provider: "ashby", slug: "notion", jobId: "uuid-xyz" });
  });

  test("parseIdentifier parses direct URLs", () => {
    const gh = parseIdentifier("https://boards.greenhouse.io/vercel/jobs/6136160004");
    expect(gh).toEqual({ provider: "greenhouse", slug: "vercel", jobId: "6136160004" });

    const lv = parseIdentifier(
      "https://jobs.lever.co/meesho/7d9af9b5-c1c7-48ec-bbb5-9b25e49f6596"
    );
    expect(lv).toEqual({
      provider: "lever",
      slug: "meesho",
      jobId: "7d9af9b5-c1c7-48ec-bbb5-9b25e49f6596",
    });

    const as = parseIdentifier(
      "https://jobs.ashbyhq.com/notion/1fc309c8-da20-4ff2-84c7-8b863ece2b0a"
    );
    expect(as).toEqual({
      provider: "ashby",
      slug: "notion",
      jobId: "1fc309c8-da20-4ff2-84c7-8b863ece2b0a",
    });
  });

  test("decodeHtmlEntities decodes entities", () => {
    expect(decodeHtmlEntities("Lead &amp; Principal &#x2f; Staff")).toBe(
      "Lead & Principal / Staff"
    );
  });

  test("cleanHtml formats markup into readable text", () => {
    const raw = "<h2>Requirements</h2><ul><li>5+ years React</li></ul>";
    const cleaned = cleanHtml(raw);
    expect(cleaned).toContain("Requirements");
    expect(cleaned).toContain("5+ years React");
  });

  test("loadWatchlist loads seeded watchlist correctly", () => {
    const watchlist = loadWatchlist();
    expect(watchlist.length).toBeGreaterThanOrEqual(10);
    expect(watchlist.some((w) => w.slug === "vercel" && w.provider === "greenhouse")).toBe(true);
    expect(watchlist.some((w) => w.slug === "notion" && w.provider === "ashby")).toBe(true);
    expect(watchlist.some((w) => w.slug === "meesho" && w.provider === "lever")).toBe(true);
  });
});
