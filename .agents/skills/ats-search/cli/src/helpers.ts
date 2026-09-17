// Helpers for querying direct company ATS boards (Greenhouse, Lever, Ashby).
// Keyless, public JSON APIs with exponential backoff and normalized output.

import { join, resolve } from "path"
import { readFileSync, existsSync } from "fs"

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

const UA = "Mozilla/5.0 (compatible; ats-search-cli/1.0)"

export type ATSProvider = "greenhouse" | "lever" | "ashby"

export interface WatchlistEntry {
  company: string
  provider: ATSProvider
  slug: string
  keywords?: string[]
}

export interface NormalizedJob {
  id: string
  site: string
  company: string
  title: string
  location: string | null
  type: string | null
  salary: string | null
  url: string
  apply_url: string
  date: string | null
  description: string | null
  provider: ATSProvider
}

export function loadWatchlist(customPath?: string): WatchlistEntry[] {
  const candidatePaths = [
    customPath,
    join(process.cwd(), "tools/ats_watchlist.json"),
    join(process.cwd(), "../../tools/ats_watchlist.json"),
    join(process.cwd(), "../../../../tools/ats_watchlist.json"),
  ].filter(Boolean) as string[]

  for (const p of candidatePaths) {
    const abs = resolve(p)
    if (existsSync(abs)) {
      try {
        const content = readFileSync(abs, "utf-8")
        return JSON.parse(content) as WatchlistEntry[]
      } catch {
        continue
      }
    }
  }

  throw new Error("Could not find tools/ats_watchlist.json. Specify --watchlist <path>")
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

export async function fetchWithBackoff(url: string): Promise<any> {
  const maxRetries = 6
  let delay = 500

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    let response: Response
    try {
      response = await fetch(url, {
        headers: { "User-Agent": UA, Accept: "application/json" },
        redirect: "follow",
        signal: AbortSignal.timeout(15000),
      })
    } catch (e) {
      throw new Error(`Connection error to ${url}: ${e instanceof Error ? e.message : String(e)}`)
    }

    if (response.status === 429 || response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`ATS request failed after retries: ${response.status} ${response.statusText}`)
      }
      await sleep(delay + Math.floor(Math.random() * 500))
      delay = Math.min(delay * 2, 8000)
      continue
    }

    if (response.status === 404) {
      return null
    }

    if (!response.ok) {
      throw new Error(`ATS request failed: ${response.status} ${response.statusText}`)
    }

    return response.json()
  }
  throw new Error("Request failed after max retries")
}

function numericEntity(cp: number): string {
  return cp >= 0 && cp <= 0x10ffff ? String.fromCodePoint(cp) : ""
}

export function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#x2f;/gi, "/")
    .replace(/&#47;/g, "/")
    .replace(/&#(\d+);/g, (_, dec) => numericEntity(parseInt(dec, 10)))
    .replace(/&#[xX]([0-9a-fA-F]+);/g, (_, hex) => numericEntity(parseInt(hex, 16)))
    .replace(/&nbsp;/g, " ")
}

export function cleanHtml(html: string | null | undefined): string | null {
  if (!html) return null
  const initialDecoded = decodeHtmlEntities(html)
  const withBreaks = initialDecoded
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\/(p|li|ul|ol|div|h\d)>/gi, "\n")
  const text = decodeHtmlEntities(withBreaks.replace(/<[^>]+>/g, " "))
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
  return text || null
}

export async function fetchGreenhouseJobs(entry: WatchlistEntry): Promise<NormalizedJob[]> {
  const url = `https://boards-api.greenhouse.io/v1/boards/${entry.slug}/jobs?content=true`
  const data = await fetchWithBackoff(url)
  if (!data || !data.jobs) return []

  return data.jobs.map((j: any) => {
    const jobId = String(j.id)
    const offices = Array.isArray(j.offices)
      ? j.offices.map((o: any) => o.location || o.name).filter(Boolean)
      : []
    const location = j.location?.name || offices.join(", ") || "Remote"
    const date = j.first_published
      ? j.first_published.slice(0, 10)
      : j.updated_at
        ? j.updated_at.slice(0, 10)
        : null

    return {
      id: `greenhouse:${entry.slug}:${jobId}`,
      site: `GREENHOUSE:${entry.company}`,
      company: entry.company,
      title: decodeHtmlEntities(j.title || "(untitled)"),
      location,
      type: null,
      salary: null,
      url: j.absolute_url,
      apply_url: j.absolute_url,
      date,
      description: cleanHtml(j.content),
      provider: "greenhouse",
    }
  })
}

export async function fetchLeverJobs(entry: WatchlistEntry): Promise<NormalizedJob[]> {
  const url = `https://api.lever.co/v0/postings/${entry.slug}?limit=100`
  const data = await fetchWithBackoff(url)
  if (!Array.isArray(data)) return []

  return data.map((j: any) => {
    const jobId = String(j.id)
    const loc = j.categories?.location || j.workplaceType || "Remote"
    const date = j.createdAt ? new Date(j.createdAt).toISOString().slice(0, 10) : null
    const desc = j.descriptionPlain || cleanHtml(j.description) || j.descriptionBodyPlain || null

    return {
      id: `lever:${entry.slug}:${jobId}`,
      site: `LEVER:${entry.company}`,
      company: entry.company,
      title: decodeHtmlEntities(j.text || "(untitled)"),
      location: loc,
      type: j.categories?.commitment || j.workplaceType || null,
      salary: null,
      url: j.hostedUrl,
      apply_url: j.applyUrl || j.hostedUrl,
      date,
      description: desc,
      provider: "lever",
    }
  })
}

export async function fetchAshbyJobs(entry: WatchlistEntry): Promise<NormalizedJob[]> {
  const url = `https://api.ashbyhq.com/posting-api/job-board/${entry.slug}?includeCompensation=true`
  const data = await fetchWithBackoff(url)
  if (!data || !data.jobs) return []

  return data.jobs.map((j: any) => {
    const jobId = String(j.id)
    const location = j.location || (j.isRemote ? "Remote" : null) || j.workplaceType || "Remote"
    const date = j.publishedAt ? j.publishedAt.slice(0, 10) : null
    const salary = j.compensation?.compensationTierSummary || j.compensation?.summary || null
    const desc = j.descriptionPlain || cleanHtml(j.descriptionHtml) || null

    return {
      id: `ashby:${entry.slug}:${jobId}`,
      site: `ASHBY:${entry.company}`,
      company: entry.company,
      title: decodeHtmlEntities(j.title || "(untitled)"),
      location,
      type: j.employmentType || j.workplaceType || null,
      salary,
      url: j.jobUrl,
      apply_url: j.applyUrl || j.jobUrl,
      date,
      description: desc,
      provider: "ashby",
    }
  })
}

export async function fetchBoardJobs(entry: WatchlistEntry): Promise<NormalizedJob[]> {
  switch (entry.provider) {
    case "greenhouse":
      return fetchGreenhouseJobs(entry)
    case "lever":
      return fetchLeverJobs(entry)
    case "ashby":
      return fetchAshbyJobs(entry)
    default:
      return []
  }
}
