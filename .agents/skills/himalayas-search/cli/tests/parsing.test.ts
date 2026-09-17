import { describe, expect, test } from "bun:test";
import {
  cleanHtml,
  decodeHtmlEntities,
  extractSlug,
  formatDate,
  formatSalary,
  toResult,
  type HimalayasJob,
} from "../src/helpers";

describe("Himalayas parsing and helper utilities", () => {
  test("extractSlug extracts the last URL segment", () => {
    expect(
      extractSlug("https://himalayas.app/companies/mercor/jobs/law-assessment-expert-7927796087")
    ).toBe("law-assessment-expert-7927796087");
    expect(extractSlug("law-assessment-expert-7927796087")).toBe(
      "law-assessment-expert-7927796087"
    );
  });

  test("decodeHtmlEntities decodes common HTML entities and hex entities", () => {
    expect(decodeHtmlEntities(".NET&#x2f;Angular &amp; React")).toBe(".NET/Angular & React");
    expect(decodeHtmlEntities("Salary &#36;100k")).toBe("Salary $100k");
  });

  test("cleanHtml strips tags and converts break tags to newlines", () => {
    const raw = "<p>First line</p><br><p>Second line</p>";
    const cleaned = cleanHtml(raw);
    expect(cleaned).toContain("First line");
    expect(cleaned).toContain("Second line");
  });

  test("formatSalary handles min, max, currency, and period", () => {
    const job: HimalayasJob = {
      title: "Dev",
      minSalary: 80000,
      maxSalary: 120000,
      currency: "USD",
      salaryPeriod: "annual",
    };
    expect(formatSalary(job)).toBe("USD 80,000–120,000 annual");

    const noSalary: HimalayasJob = { title: "Dev" };
    expect(formatSalary(noSalary)).toBeNull();
  });

  test("formatDate converts Unix timestamp in seconds to YYYY-MM-DD", () => {
    // 1789383447 seconds -> 2026-09-14
    const d = formatDate(1789383447);
    expect(d).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(formatDate(undefined)).toBeNull();
  });

  test("toResult reshapes HimalayasJob into canonical JobResult", () => {
    const job: HimalayasJob = {
      title: "Senior Developer",
      companyName: "Tech Corp",
      employmentType: "Full Time",
      pubDate: 1789383447,
      applicationLink: "https://himalayas.app/companies/tech/jobs/senior-developer-99",
      locationRestrictions: ["India", "Remote"],
      minSalary: 50000,
      maxSalary: 70000,
      currency: "USD",
      salaryPeriod: "annual",
    };
    const res = toResult(job);
    expect(res.id).toBe("senior-developer-99");
    expect(res.site).toBe("himalayas");
    expect(res.title).toBe("Senior Developer");
    expect(res.company).toBe("Tech Corp");
    expect(res.location).toBe("India, Remote");
    expect(res.type).toBe("Full Time");
    expect(res.salary).toBe("USD 50,000–70,000 annual");
    expect(res.url).toBe("https://himalayas.app/companies/tech/jobs/senior-developer-99");
    expect(res.apply_url).toBe("https://himalayas.app/companies/tech/jobs/senior-developer-99");
    expect(res.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
