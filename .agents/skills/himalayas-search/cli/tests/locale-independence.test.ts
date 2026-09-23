import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { formatSalary, type HimalayasJob } from "../src/helpers";

// Salary strings are part of the CLI contract, so they must not depend on the
// host's default locale: on a Danish host a bare toLocaleString() renders 120000
// as "120.000", and three tests in this CLI used to fail on exactly that machine.
describe("Himalayas salary formatting is independent of the machine locale", () => {
  const original = Number.prototype.toLocaleString;

  beforeEach(() => {
    // Simulate a host whose default locale is Danish: any toLocaleString() call
    // that does not pass a locale argument gets da-DK here.
    Number.prototype.toLocaleString = function (
      this: number,
      locales?: string | string[],
      options?: Intl.NumberFormatOptions
    ): string {
      return new Intl.NumberFormat(locales ?? "da-DK", options).format(this);
    };
  });

  afterEach(() => {
    Number.prototype.toLocaleString = original;
  });

  test("the simulated default really is Danish", () => {
    expect((120000).toLocaleString()).toBe("120.000");
  });

  test("a Danish host default does not leak into a ranged salary string", () => {
    const job: HimalayasJob = {
      title: "Dev",
      minSalary: 120000,
      maxSalary: 150000,
      currency: "USD",
      salaryPeriod: "annual",
    };
    expect(formatSalary(job)).toBe("USD 120,000–150,000 annual");
  });

  test("a single-ended salary is pinned the same way", () => {
    const job: HimalayasJob = {
      title: "Dev",
      minSalary: 120000,
      currency: "USD",
    };
    expect(formatSalary(job)).toBe("USD 120,000");
  });
});
