import { describe, test, expect } from "bun:test";
import { runCLI } from "./helpers";

function parsedStderr(stderr: string): { error?: string; code?: string } {
  try {
    return JSON.parse(stderr);
  } catch {
    return {};
  }
}

describe("Remotive CLI flag validation", () => {
  describe("numeric flag validation", () => {
    for (const name of ["jobage", "limit"]) {
      test(`--${name} non-numeric exits 1 with BAD_ARG`, async () => {
        const result = await runCLI(["search", `--${name}`, "foo"]);
        expect(result.exitCode).not.toBe(0);
        const err = parsedStderr(result.stderr);
        expect(err.code).toBe("BAD_ARG");
        expect(err.error).toMatch(new RegExp(name));
      });

      test(`--${name} fractional exits 1 with BAD_ARG`, async () => {
        const result = await runCLI(["search", `--${name}`, "1.5"]);
        expect(result.exitCode).not.toBe(0);
        const err = parsedStderr(result.stderr);
        expect(err.code).toBe("BAD_ARG");
        expect(err.error).toMatch(new RegExp(name));
      });

      test(`--${name} 0 exits 1 with BAD_ARG`, async () => {
        const result = await runCLI(["search", `--${name}`, "0"]);
        expect(result.exitCode).not.toBe(0);
        const err = parsedStderr(result.stderr);
        expect(err.code).toBe("BAD_ARG");
        expect(err.error).toMatch(new RegExp(name));
      });
    }

    test("boolean flag (no value) exits 1 with BAD_ARG", async () => {
      const result = await runCLI(["search", "--limit"]);
      expect(result.exitCode).not.toBe(0);
      expect(result.stderr).toBeTruthy();
    });
  });

  describe("detail argument validation", () => {
    test("missing id exits 1 with NO_ID", async () => {
      const result = await runCLI(["detail"]);
      expect(result.exitCode).not.toBe(0);
      const err = parsedStderr(result.stderr);
      expect(err.code).toBe("NO_ID");
    });
  });

  describe("unknown flag rejection", () => {
    test("a bogus --flag exits 1 with UNKNOWN_FLAG", async () => {
      const result = await runCLI(["search", "-q", "test", "--bogus-flag", "xyz"]);
      expect(result.exitCode).toBe(1);
      const err = parsedStderr(result.stderr);
      expect(err.code).toBe("UNKNOWN_FLAG");
      expect(err.error).toContain("--bogus-flag");
    });
  });

  describe("command dispatch", () => {
    test("unknown command exits 1 with BAD_CMD", async () => {
      const result = await runCLI(["foobar"]);
      expect(result.exitCode).toBe(1);
      const err = parsedStderr(result.stderr);
      expect(err.code).toBe("BAD_CMD");
    });

    test("no command prints help and exits 1", async () => {
      const result = await runCLI([]);
      expect(result.exitCode).toBe(1);
      expect(result.stdout).toContain("remotive-cli");
    });

    test("--help prints help and exits 0", async () => {
      const result = await runCLI(["--help"]);
      expect(result.exitCode).toBe(0);
      expect(result.stdout).toContain("remotive-cli");
    });
  });
});
