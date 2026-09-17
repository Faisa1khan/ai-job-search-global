import {
  apiGet,
  cleanHtml,
  extractSlug,
  toResult,
  writeError,
  type HimalayasJob,
  type JobResult,
} from "../helpers.js"

export interface DetailOpts {
  id: string
  format: "json" | "plain"
}

export interface DetailResult extends JobResult {
  fullDescription: string | null
  categories: string[]
  timezoneRestrictions?: number[]
}

function matchesIdentifier(job: HimalayasJob, target: string): boolean {
  const t = target.toLowerCase().trim()
  const rawUrl = (job.applicationLink || job.guid || "").toLowerCase()
  const slug = extractSlug(rawUrl).toLowerCase()

  if (rawUrl === t || slug === t) return true
  if (slug.endsWith(t) || t.endsWith(slug)) return true

  // Check if target is a numeric ID at the end of the slug
  const numMatch = slug.match(/(\d{6,})$/)
  if (numMatch && numMatch[1] === t) return true

  return false
}

function renderPlain(job: DetailResult): string {
  const lines = [
    job.title,
    `${job.company ?? "—"} · ${job.location ?? "—"}`,
    "",
    job.date ? `Posted: ${job.date}` : "",
    job.seniority ? `Seniority: ${job.seniority}` : "",
    job.type ? `Employment: ${job.type}` : "",
    job.salary ? `Salary: ${job.salary}` : "",
    job.categories && job.categories.length > 0 ? `Categories: ${job.categories.join(", ")}` : "",
    "",
    job.fullDescription || job.description || "(no description)",
    "",
    `Apply URL: ${job.apply_url}`,
    `ID: ${job.id}`,
  ].filter((l) => l !== "")

  return lines.join("\n")
}

export async function runDetail(opts: DetailOpts): Promise<number> {
  const target = opts.id.trim()
  if (!target) {
    writeError("detail requires an <id|slug|url>", "NO_ID")
    return 1
  }

  try {
    // Scan up to 5 pages (100 jobs) from Himalayas API
    let foundJob: HimalayasJob | null = null
    const pageSize = 20

    for (let p = 0; p < 5; p++) {
      const data = await apiGet({ limit: pageSize, offset: p * pageSize })
      const jobs = data.jobs || []
      if (jobs.length === 0) break

      for (const job of jobs) {
        if (matchesIdentifier(job, target)) {
          foundJob = job
          break
        }
      }
      if (foundJob) break
    }

    if (!foundJob) {
      writeError(`Job not found for "${target}"`, "NOT_FOUND")
      return 1
    }

    const base = toResult(foundJob)
    const detailResult: DetailResult = {
      ...base,
      fullDescription: cleanHtml(foundJob.description) || base.description,
      categories: foundJob.categories || [],
      timezoneRestrictions: foundJob.timezoneRestrictions,
    }

    if (opts.format === "plain") {
      process.stdout.write(renderPlain(detailResult) + "\n")
    } else {
      process.stdout.write(JSON.stringify(detailResult, null, 2) + "\n")
    }
    return 0
  } catch (e) {
    writeError(e instanceof Error ? e.message : String(e), "DETAIL_FAILED")
    return 1
  }
}
