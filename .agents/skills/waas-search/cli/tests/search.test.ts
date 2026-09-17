import { describe, expect, test } from "bun:test"
import { runCLI, parseJSON } from "./helpers.js"
import { unescapeHtml, htmlToPlain, parseDataPage, mapRawToCard } from "../src/helpers.js"
import { normalizeId } from "../src/commands/detail.js"

describe("waas-cli flag validation", () => {
  test("unknown flag exits 1 with UNKNOWN_FLAG on stderr", async () => {
    const res = await runCLI(["search", "--bogus-flag"])
    expect(res.exitCode).toBe(1)
    const err = JSON.parse(res.stderr)
    expect(err.code).toBe("UNKNOWN_FLAG")
    expect(err.error).toContain("--bogus-flag")
  })

  test("invalid --limit exits 1 with BAD_ARG on stderr", async () => {
    const res = await runCLI(["search", "--limit", "abc"])
    expect(res.exitCode).toBe(1)
    const err = JSON.parse(res.stderr)
    expect(err.code).toBe("BAD_ARG")
  })

  test("negative --limit exits 1 with BAD_ARG on stderr", async () => {
    const res = await runCLI(["search", "--limit", "-5"])
    expect(res.exitCode).toBe(1)
    const err = JSON.parse(res.stderr)
    expect(err.code).toBe("BAD_ARG")
  })

  test("detail without ID exits 1 with NO_ID on stderr", async () => {
    const res = await runCLI(["detail"])
    expect(res.exitCode).toBe(1)
    const err = JSON.parse(res.stderr)
    expect(err.code).toBe("NO_ID")
  })

  test("--help exits 0 and prints usage", async () => {
    const res = await runCLI(["--help"])
    expect(res.exitCode).toBe(0)
    expect(res.stdout).toContain("waas-cli")
    expect(res.stdout).toContain("SEARCH FLAGS")
  })
})

describe("waas-cli helpers", () => {
  test("normalizeId extracts numeric ID from raw string or URL", () => {
    expect(normalizeId("67196")).toBe("67196")
    expect(normalizeId("https://www.workatastartup.com/jobs/67196")).toBe("67196")
    expect(normalizeId("https://www.workatastartup.com/jobs/13302?query=test")).toBe("13302")
    expect(normalizeId("invalid-id")).toBe(null)
  })

  test("unescapeHtml unescapes standard entities", () => {
    const escaped = "&quot;Hello &amp; World&#39;&quot; &lt;div&gt;"
    expect(unescapeHtml(escaped)).toBe('"Hello & World\'" <div>')
  })

  test("htmlToPlain strips tags and preserves paragraphs", () => {
    const html = "<p>First paragraph.</p><p>Second paragraph with <b>bold</b> text.</p><ul><li>Item 1</li><li>Item 2</li></ul>"
    const plain = htmlToPlain(html)
    expect(plain).toContain("First paragraph.")
    expect(plain).toContain("Second paragraph with bold text.")
    expect(plain).toContain("• Item 1")
    expect(plain).toContain("• Item 2")
  })

  test("parseDataPage extracts Inertia payload", () => {
    const html = '<div data-page="{&quot;component&quot;:&quot;JobsPage&quot;,&quot;props&quot;:{&quot;jobs&quot;:[{&quot;id&quot;:123,&quot;title&quot;:&quot;Engineer&quot;}]}}"></div>'
    const data = parseDataPage(html)
    expect(data).not.toBe(null)
    expect(data.component).toBe("JobsPage")
    expect(data.props.jobs[0].id).toBe(123)
  })

  test("mapRawToCard maps fields and computes remote flag", () => {
    const card = mapRawToCard({
      id: 456,
      title: "Fullstack Dev",
      companyName: "Acme",
      companyBatch: "W24",
      location: "San Francisco, CA / Remote",
      roleType: "Full stack",
      salary: "$150K",
    })
    expect(card.id).toBe("456")
    expect(card.title).toBe("Fullstack Dev")
    expect(card.company).toBe("Acme")
    expect(card.batch).toBe("W24")
    expect(card.remote).toBe(true)
    expect(card.category).toBe("Full stack")
    expect(card.salary).toBe("$150K")
    expect(card.url).toBe("https://www.workatastartup.com/jobs/456")
  })
})

describe("waas-cli live smoke queries", () => {
  test("live search returns results matching schema", async () => {
    const res = await runCLI([
      "search",
      "--query",
      "frontend engineer",
      "--remote",
      "--limit",
      "3",
      "--format",
      "json",
    ])
    const data = parseJSON<{ meta: { count: number }; results: Array<any> }>(res)
    expect(data.meta.count).toBeGreaterThanOrEqual(1)
    expect(data.results.length).toBeGreaterThanOrEqual(1)

    const first = data.results[0]
    expect(first.id).toBeDefined()
    expect(first.title).toBeDefined()
    expect(first.company).toBeDefined()
    expect(first.remote).toBe(true)
    expect(first.url).toContain("workatastartup.com/jobs/")
  })
})
