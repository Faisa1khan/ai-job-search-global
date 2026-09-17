import { fetchJobs, writeError, type WaasJobCard } from "../helpers.js"

export interface SearchOpts {
  query?: string
  remote?: boolean
  limit?: number
  format: "json" | "table" | "plain"
}

export function renderTable(cards: WaasJobCard[]): string {
  if (cards.length === 0) return "No results."
  const rows = cards.map((c) => {
    const id = c.id.padEnd(8)
    const title = (c.title || "").slice(0, 35).padEnd(35)
    const company = (c.company || "—").slice(0, 20).padEnd(20)
    const batch = (c.batch || "—").slice(0, 5).padEnd(5)
    const loc = (c.location || "—").slice(0, 25).padEnd(25)
    const remote = (c.remote ? "yes" : "no").padEnd(6)
    const category = (c.category || "—").slice(0, 14).padEnd(14)
    const salary = c.salary || "—"
    return `${id} ${title} ${company} ${batch} ${loc} ${remote} ${category} ${salary}`
  })
  const header =
    "ID".padEnd(8) +
    " " +
    "TITLE".padEnd(35) +
    " " +
    "COMPANY".padEnd(20) +
    " " +
    "BATCH".padEnd(5) +
    " " +
    "LOCATION".padEnd(25) +
    " " +
    "REMOTE".padEnd(6) +
    " " +
    "CATEGORY".padEnd(14) +
    " " +
    "SALARY"
  return [header, "-".repeat(header.length), ...rows].join("\n")
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  try {
    const cards = await fetchJobs({
      query: opts.query,
      remote: opts.remote,
      limit: opts.limit,
    })

    if (opts.format === "table") {
      process.stdout.write(renderTable(cards) + "\n")
    } else if (opts.format === "plain") {
      if (cards.length === 0) {
        process.stdout.write("No results.\n")
      } else {
        process.stdout.write(
          cards
            .map(
              (c) =>
                `${c.title}\n  ${c.company} (${c.batch || "—"}) · ${c.location || "—"} · ${c.category || "—"} · ${c.salary || "Salary not listed"}\n  id: ${c.id} · remote: ${c.remote ? "yes" : "no"}\n  ${c.url}`,
            )
            .join("\n\n") + "\n",
        )
      }
    } else {
      process.stdout.write(
        JSON.stringify(
          { meta: { count: cards.length }, results: cards },
          null,
          2,
        ) + "\n",
      )
    }
    return 0
  } catch (e) {
    writeError(e instanceof Error ? e.message : String(e), "SEARCH_FAILED")
    return 1
  }
}
