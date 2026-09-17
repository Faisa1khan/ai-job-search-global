import {
  apiGet,
  cleanHtml,
  extractId,
  toResult,
  writeError,
  type RemotiveJob,
  type JobResult,
} from "../helpers.js"

export interface DetailOpts {
  id: string
  format: "json" | "plain"
}

export interface DetailResult extends JobResult {
  fullDescription: string | null
  tags: string[]
  companyLogo?: string
}

function renderPlain(job: DetailResult): string {
  const lines = [
    job.title,
    `${job.company ?? "—"} · ${job.location ?? "—"}`,
    "",
    job.date ? `Posted: ${job.date}` : "",
    job.type ? `Type: ${job.type}` : "",
    job.category ? `Category: ${job.category}` : "",
    job.salary ? `Salary: ${job.salary}` : "",
    job.tags && job.tags.length > 0 ? `Tags: ${job.tags.join(", ")}` : "",
    "",
    job.fullDescription || job.description || "(no description)",
    "",
    `URL: ${job.url}`,
    `ID: ${job.id}`,
  ].filter((l) => l !== "")

  return lines.join("\n")
}

export async function runDetail(opts: DetailOpts): Promise<number> {
  const idStr = extractId(opts.id)
  if (!idStr) {
    writeError(`Could not parse a job ID from "${opts.id}"`, "BAD_ID")
    return 1
  }
  const numericId = parseInt(idStr, 10)

  try {
    const data = await apiGet()
    const jobs = data.jobs || []
    const foundJob = jobs.find((j) => j.id === numericId || String(j.id) === idStr)

    if (!foundJob) {
      writeError(`Job not found for ID "${opts.id}"`, "NOT_FOUND")
      return 1
    }

    const base = toResult(foundJob)
    const detailResult: DetailResult = {
      ...base,
      fullDescription: cleanHtml(foundJob.description) || base.description,
      tags: foundJob.tags || [],
      companyLogo: foundJob.company_logo_url || foundJob.company_logo,
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
