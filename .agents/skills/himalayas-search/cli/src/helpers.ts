// Data source: Himalayas public jobs API (GET https://himalayas.app/jobs/api)
// No authentication required — public, keyless JSON endpoint.

export const DEFAULT_API_URL = "https://himalayas.app/jobs/api"

export function apiUrl(): string {
  const raw = (process.env.HIMALAYAS_API_URL ?? "").trim()
  return raw || DEFAULT_API_URL
}

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

const UA = "Mozilla/5.0 (compatible; himalayas-search-cli/1.0)"

export interface HimalayasJob {
  title: string
  excerpt?: string
  companyName?: string
  companySlug?: string
  companyLogo?: string
  employmentType?: string
  minSalary?: number | null
  maxSalary?: number | null
  salaryPeriod?: string | null
  seniority?: string[]
  currency?: string | null
  locationRestrictions?: string[]
  timezoneRestrictions?: number[]
  categories?: string[]
  parentCategories?: string[]
  description?: string
  pubDate?: number
  expiryDate?: number
  applicationLink?: string
  guid?: string
}

export interface HimalayasResponse {
  jobs?: HimalayasJob[]
  limit?: number
  offset?: number
  totalCount?: number
  updatedAt?: number
}

export interface JobResult {
  id: string
  site: "himalayas"
  title: string
  company: string | null
  location: string | null
  type: string | null
  salary: string | null
  url: string
  apply_url: string
  date: string | null
  description: string | null
  seniority: string | null
  categories: string[]
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/**
 * Fetch Himalayas jobs API with backoff on 429/5xx.
 */
export async function apiGet(params: Record<string, string | number>): Promise<HimalayasResponse> {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    query.set(k, String(v))
  }
  const url = `${apiUrl()}?${query.toString()}`

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
      throw new Error(
        `could not reach the Himalayas API at ${apiUrl()} (${e instanceof Error ? e.message : String(e)})`,
      )
    }

    if (response.status === 429 || response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Himalayas API request failed: ${response.status} ${response.statusText}`)
      }
      await sleep(delay + Math.floor(Math.random() * 500))
      delay = Math.min(delay * 2, 8000)
      continue
    }

    if (response.status === 404) {
      throw new Error(`Himalayas API endpoint not found: 404 ${response.statusText}`)
    }

    if (!response.ok) {
      throw new Error(`Himalayas API request failed: ${response.status} ${response.statusText}`)
    }

    const data = (await response.json().catch(() => null)) as HimalayasResponse | null
    if (!data) {
      throw new Error("Himalayas API returned unparseable JSON")
    }
    return data
  }
  throw new Error("Himalayas API request failed after retries")
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

export function formatSalary(job: HimalayasJob): string | null {
  if (job.minSalary == null && job.maxSalary == null) return null
  const cur = job.currency ? `${job.currency} ` : "$"
  const period = job.salaryPeriod ? ` ${job.salaryPeriod}` : ""
  // The salary string is part of the CLI contract, so the grouping separator must
  // not follow the machine's locale: pin en-US (120,000) instead of the host default
  // (a da-DK host would render 120.000 and break the tests and every consumer).
  if (job.minSalary != null && job.maxSalary != null) {
    return `${cur}${job.minSalary.toLocaleString("en-US")}–${job.maxSalary.toLocaleString("en-US")}${period}`
  }
  const val = (job.minSalary ?? job.maxSalary)!
  return `${cur}${val.toLocaleString("en-US")}${period}`
}

export function formatDate(pubDate: number | undefined): string | null {
  if (!pubDate) return null
  // pubDate is a Unix timestamp in seconds
  const ms = pubDate > 1e11 ? pubDate : pubDate * 1000
  const d = new Date(ms)
  if (isNaN(d.getTime())) return null
  return d.toISOString().slice(0, 10)
}

export function extractSlug(input: string): string {
  const trimmed = input.trim()
  // If it's a URL, extract the last path segment
  if (trimmed.includes("/")) {
    const parts = trimmed.split(/[?#]/)[0].split("/").filter(Boolean)
    return parts[parts.length - 1] || trimmed
  }
  return trimmed
}

export function toResult(job: HimalayasJob): JobResult {
  const rawUrl = job.applicationLink || job.guid || ""
  const id = extractSlug(rawUrl) || String(job.pubDate || Math.random())
  const location =
    job.locationRestrictions && job.locationRestrictions.length > 0
      ? job.locationRestrictions.join(", ")
      : "Worldwide / Remote"

  return {
    id,
    site: "himalayas",
    title: decodeHtmlEntities(job.title || "(untitled)"),
    company: job.companyName ? decodeHtmlEntities(job.companyName) : null,
    location,
    type: job.employmentType || null,
    salary: formatSalary(job),
    url: rawUrl,
    apply_url: rawUrl,
    date: formatDate(job.pubDate),
    description: cleanHtml(job.description) || job.excerpt || null,
    seniority: job.seniority && job.seniority.length > 0 ? job.seniority[0] : null,
    categories: job.categories || [],
  }
}
