import {
  cleanHtml,
  decodeHtmlEntities,
  fetchWithBackoff,
  loadWatchlist,
  writeError,
  type ATSProvider,
  type NormalizedJob,
} from "../helpers.js"

export interface DetailOpts {
  id: string
  format: "json" | "plain"
  watchlist?: string
}

interface ParsedIdentifier {
  provider: ATSProvider
  slug: string
  jobId: string
  company?: string
}

export function parseIdentifier(raw: string, watchlistCustomPath?: string): ParsedIdentifier | null {
  const trimmed = raw.trim()

  // Case 1: Composite ID format: provider:slug:jobId
  const composite = trimmed.match(/^(greenhouse|lever|ashby):([^:]+):(.+)$/i)
  if (composite) {
    const provider = composite[1].toLowerCase() as ATSProvider
    const slug = composite[2]
    const jobId = composite[3]
    return { provider, slug, jobId }
  }

  // Case 2: Direct Greenhouse URL: https://boards.greenhouse.io/<slug>/jobs/<jobId>
  const gh = trimmed.match(/boards\.greenhouse\.io\/([^\/]+)\/jobs\/(\d+)/i)
  if (gh) {
    return { provider: "greenhouse", slug: gh[1], jobId: gh[2] }
  }

  // Case 3: Direct Lever URL: https://jobs.lever.co/<slug>/<jobId>
  const lv = trimmed.match(/jobs\.lever\.co\/([^\/]+)\/([^\/?#]+)/i)
  if (lv) {
    return { provider: "lever", slug: lv[1], jobId: lv[2] }
  }

  // Case 4: Direct Ashby URL: https://jobs.ashbyhq.com/<slug>/<jobId>
  const ashby = trimmed.match(/jobs\.ashbyhq\.com\/([^\/]+)\/([^\/?#]+)/i)
  if (ashby) {
    return { provider: "ashby", slug: ashby[1], jobId: ashby[2] }
  }

  return null
}

function renderPlain(job: NormalizedJob): string {
  const lines = [
    job.title,
    `${job.site} · ${job.location ?? "—"}`,
    "",
    job.date ? `Posted: ${job.date}` : "",
    job.type ? `Employment: ${job.type}` : "",
    job.salary ? `Salary: ${job.salary}` : "",
    "",
    job.description || "(no description)",
    "",
    `Apply URL: ${job.apply_url}`,
    `ID: ${job.id}`,
  ].filter((l) => l !== "")

  return lines.join("\n")
}

export async function runDetail(opts: DetailOpts): Promise<number> {
  const target = opts.id.trim()
  if (!target) {
    writeError("detail requires an <id|url>", "NO_ID")
    return 1
  }

  let parsed = parseIdentifier(target, opts.watchlist)

  // If bare ID, check watchlist companies to find which board it belongs to
  if (!parsed) {
    try {
      const watchlist = loadWatchlist(opts.watchlist)
      for (const entry of watchlist) {
        if (entry.provider === "greenhouse" && /^\d+$/.test(target)) {
          const check = await fetchWithBackoff(
            `https://boards-api.greenhouse.io/v1/boards/${entry.slug}/jobs/${target}`,
          )
          if (check && check.id) {
            parsed = { provider: "greenhouse", slug: entry.slug, jobId: target, company: entry.company }
            break
          }
        } else if (entry.provider === "lever") {
          const check = await fetchWithBackoff(
            `https://api.lever.co/v0/postings/${entry.slug}/${target}`,
          )
          if (check && check.id) {
            parsed = { provider: "lever", slug: entry.slug, jobId: target, company: entry.company }
            break
          }
        } else if (entry.provider === "ashby") {
          const board = await fetchWithBackoff(
            `https://api.ashbyhq.com/posting-api/job-board/${entry.slug}?includeCompensation=true`,
          )
          if (board && board.jobs && board.jobs.some((j: any) => j.id === target)) {
            parsed = { provider: "ashby", slug: entry.slug, jobId: target, company: entry.company }
            break
          }
        }
      }
    } catch {
      // Continue to not found
    }
  }

  if (!parsed) {
    writeError(`Could not identify ATS provider or company from "${target}"`, "BAD_ID")
    return 1
  }

  try {
    let job: NormalizedJob | null = null
    const company = parsed.company || parsed.slug

    if (parsed.provider === "greenhouse") {
      const data = await fetchWithBackoff(
        `https://boards-api.greenhouse.io/v1/boards/${parsed.slug}/jobs/${parsed.jobId}?questions=true`,
      )
      if (data && data.id) {
        const offices = Array.isArray(data.offices)
          ? data.offices.map((o: any) => o.location || o.name).filter(Boolean)
          : []
        job = {
          id: `greenhouse:${parsed.slug}:${data.id}`,
          site: `GREENHOUSE:${company}`,
          company: data.company_name || company,
          title: decodeHtmlEntities(data.title || "(untitled)"),
          location: data.location?.name || offices.join(", ") || "Remote",
          type: data.employment_type || null,
          salary: null,
          url: data.absolute_url,
          apply_url: data.absolute_url,
          date: data.first_published ? data.first_published.slice(0, 10) : null,
          description: cleanHtml(data.content),
          provider: "greenhouse",
        }
      }
    } else if (parsed.provider === "lever") {
      const data = await fetchWithBackoff(
        `https://api.lever.co/v0/postings/${parsed.slug}/${parsed.jobId}`,
      )
      if (data && data.id) {
        job = {
          id: `lever:${parsed.slug}:${data.id}`,
          site: `LEVER:${company}`,
          company,
          title: decodeHtmlEntities(data.text || "(untitled)"),
          location: data.categories?.location || data.workplaceType || "Remote",
          type: data.categories?.commitment || data.workplaceType || null,
          salary: null,
          url: data.hostedUrl,
          apply_url: data.applyUrl || data.hostedUrl,
          date: data.createdAt ? new Date(data.createdAt).toISOString().slice(0, 10) : null,
          description:
            data.descriptionPlain || cleanHtml(data.description) || data.descriptionBodyPlain || null,
          provider: "lever",
        }
      }
    } else if (parsed.provider === "ashby") {
      const board = await fetchWithBackoff(
        `https://api.ashbyhq.com/posting-api/job-board/${parsed.slug}?includeCompensation=true`,
      )
      if (board && board.jobs) {
        const j = board.jobs.find((item: any) => item.id === parsed!.jobId)
        if (j) {
          job = {
            id: `ashby:${parsed.slug}:${j.id}`,
            site: `ASHBY:${company}`,
            company,
            title: decodeHtmlEntities(j.title || "(untitled)"),
            location: j.location || (j.isRemote ? "Remote" : null) || j.workplaceType || "Remote",
            type: j.employmentType || j.workplaceType || null,
            salary: j.compensation?.compensationTierSummary || j.compensation?.summary || null,
            url: j.jobUrl,
            apply_url: j.applyUrl || j.jobUrl,
            date: j.publishedAt ? j.publishedAt.slice(0, 10) : null,
            description: j.descriptionPlain || cleanHtml(j.descriptionHtml) || null,
            provider: "ashby",
          }
        }
      }
    }

    if (!job) {
      writeError(`Job not found for ID "${target}"`, "NOT_FOUND")
      return 1
    }

    if (opts.format === "plain") {
      process.stdout.write(renderPlain(job) + "\n")
    } else {
      process.stdout.write(JSON.stringify(job, null, 2) + "\n")
    }
    return 0
  } catch (e) {
    writeError(e instanceof Error ? e.message : String(e), "DETAIL_FAILED")
    return 1
  }
}
