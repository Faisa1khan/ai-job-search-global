import {
  apiGet,
  toResult,
  writeError,
  type RemotiveJob,
  type JobResult,
} from "../helpers.js"

export interface SearchOpts {
  query?: string
  category?: string
  jobage?: number
  location?: string
  limit: number
  format: "json" | "table" | "plain"
}

function matchesQuery(job: RemotiveJob, query: string): boolean {
  const q = query.toLowerCase()
  const title = (job.title || "").toLowerCase()
  const company = (job.company_name || "").toLowerCase()
  const category = (job.category || "").toLowerCase()
  const tags = (job.tags || []).map((t) => t.toLowerCase()).join(" ")
  const desc = (job.description || "").toLowerCase()

  if (title.includes(q) || company.includes(q) || category.includes(q) || tags.includes(q) || desc.includes(q)) {
    return true
  }

  const words = q.split(/\s+/).filter(Boolean)
  if (words.length > 1) {
    const hay = `${title} ${company} ${category} ${tags} ${desc}`
    return words.every((w) => hay.includes(w))
  }

  return false
}

function matchesCategory(job: RemotiveJob, category: string): boolean {
  const cat = category.toLowerCase().replace(/[-\s]+/g, "")
  const jobCat = (job.category || "").toLowerCase().replace(/[-\s]+/g, "")
  return jobCat.includes(cat) || cat.includes(jobCat)
}

function matchesLocation(job: RemotiveJob, location: string): boolean {
  const loc = location.toLowerCase()
  const jobLoc = (job.candidate_required_location || "").toLowerCase()
  if (!jobLoc || jobLoc === "worldwide" || jobLoc === "anywhere") return true
  return jobLoc.includes(loc)
}

function matchesJobage(job: RemotiveJob, days: number): boolean {
  if (!job.publication_date || days <= 0 || days >= 9999) return true
  const pubTime = new Date(job.publication_date).getTime()
  if (isNaN(pubTime)) return true
  const ageMs = Date.now() - pubTime
  return ageMs <= days * 24 * 60 * 60 * 1000
}

function shortDate(date: string | null): string {
  return date ? date.slice(0, 10) : "—"
}

interface Column {
  header: string
  width: number
  cell: (r: JobResult) => string
}

function renderTable(rows: JobResult[]): string {
  if (rows.length === 0) return "No results."
  const columns: Column[] = [
    { header: "ID", width: 10, cell: (r) => r.id },
    { header: "TITLE", width: 38, cell: (r) => r.title },
    { header: "COMPANY", width: 22, cell: (r) => r.company ?? "—" },
    { header: "LOCATION", width: 22, cell: (r) => r.location ?? "—" },
    { header: "DATE", width: 10, cell: (r) => shortDate(r.date) },
  ]
  const row = (cells: string[]) =>
    cells.map((c, i) => c.slice(0, columns[i].width).padEnd(columns[i].width)).join("  ")

  const header = row(columns.map((c) => c.header))
  const body = rows.map((r) => row(columns.map((c) => c.cell(r))))
  return [header, "-".repeat(header.length), ...body].join("\n")
}

function renderPlain(rows: JobResult[]): string {
  if (rows.length === 0) return "No results."
  return rows
    .map((r) =>
      [
        r.title,
        `  ${r.company ?? "—"} · ${r.location ?? "—"} · ${shortDate(r.date)}`,
        r.salary ? `  Salary: ${r.salary}` : "",
        `  id: ${r.id}`,
        `  ${r.url}`,
      ]
        .filter(Boolean)
        .join("\n"),
    )
    .join("\n\n")
}

export async function runSearch(opts: SearchOpts): Promise<number> {
  try {
    const params: Record<string, string | number> = {}
    if (opts.category) params.category = opts.category
    if (opts.query) params.search = opts.query

    const data = await apiGet(params)
    const jobs = data.jobs || []
    const matching: RemotiveJob[] = []
    const seenIds = new Set<string>()

    for (const job of jobs) {
      const id = String(job.id)
      if (seenIds.has(id)) continue
      seenIds.add(id)

      if (opts.query && !matchesQuery(job, opts.query)) continue
      if (opts.category && !matchesCategory(job, opts.category)) continue
      if (opts.location && !matchesLocation(job, opts.location)) continue
      if (opts.jobage !== undefined && !matchesJobage(job, opts.jobage)) continue

      matching.push(job)
      if (matching.length >= opts.limit) break
    }

    const results = matching.slice(0, opts.limit).map(toResult)

    if (opts.format === "table") {
      process.stdout.write(renderTable(results) + "\n")
    } else if (opts.format === "plain") {
      process.stdout.write(renderPlain(results) + "\n")
    } else {
      process.stdout.write(
        JSON.stringify(
          {
            meta: {
              count: results.length,
              total: data["total-job-count"] ?? jobs.length,
            },
            results,
          },
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
