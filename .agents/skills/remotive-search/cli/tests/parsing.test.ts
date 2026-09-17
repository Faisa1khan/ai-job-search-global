import { describe, expect, test } from "bun:test";
import {
  cleanHtml,
  decodeHtmlEntities,
  extractId,
  toResult,
  type RemotiveJob,
} from "../src/helpers";

describe("Remotive parsing and helper utilities", () => {
  test("extractId extracts numeric id from various formats", () => {
    expect(extractId("2069746")).toBe("2069746");
    expect(extractId("https://remotive.com/remote-jobs/software-dev/senior-fullstack-2069746")).toBe(
      "2069746"
    );
    expect(extractId("https://remotive.com/job/2069746/apply")).toBe("2069746");
  });

  test("decodeHtmlEntities decodes entities", () => {
    expect(decodeHtmlEntities("Frontend &amp; Backend &#38; Fullstack")).toBe(
      "Frontend & Backend & Fullstack"
    );
  });

  test("cleanHtml strips tags and converts breaks to newlines", () => {
    const raw = "<h3>Role</h3><p>Build scalable systems</p>";
    const cleaned = cleanHtml(raw);
    expect(cleaned).toContain("Role");
    expect(cleaned).toContain("Build scalable systems");
  });

  test("toResult reshapes RemotiveJob into canonical JobResult", () => {
    const job: RemotiveJob = {
      id: 554433,
      url: "https://remotive.com/remote-jobs/software-dev/frontend-developer-554433",
      title: "Senior React Developer",
      company_name: "Fintech Co",
      category: "Software Development",
      tags: ["react", "typescript"],
      job_type: "full_time",
      publication_date: "2026-09-14T12:00:00",
      candidate_required_location: "Worldwide",
      salary: "$130k - $160k",
      description: "<p>Great role</p>",
    };

    const res = toResult(job);
    expect(res.id).toBe("554433");
    expect(res.site).toBe("remotive");
    expect(res.title).toBe("Senior React Developer");
    expect(res.company).toBe("Fintech Co");
    expect(res.location).toBe("Worldwide");
    expect(res.type).toBe("full time");
    expect(res.salary).toBe("$130k - $160k");
    expect(res.url).toBe("https://remotive.com/remote-jobs/software-dev/frontend-developer-554433");
    expect(res.date).toBe("2026-09-14");
    expect(res.tags).toEqual(["react", "typescript"]);
  });
});
