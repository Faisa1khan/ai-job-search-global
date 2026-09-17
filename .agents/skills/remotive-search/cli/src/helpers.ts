// Data source: Remotive public remote jobs API (GET https://remotive.com/api/remote-jobs)
// No authentication required — public, keyless JSON endpoint.

export const DEFAULT_API_URL = "https://remotive.com/api/remote-jobs"

export function apiUrl(): string {
  const raw = (process.env.REMOTIVE_API_URL ?? "").trim()
  return raw || DEFAULT_API_URL
}

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

const UA = "Mozilla/5.0 (compatible; remotive-search-cli/1.0)"

export interface RemotiveJob {
  id: number
  url: string
  title: string
  company_name: string
  company_logo?: string
  category?: string
  tags?: string[]
  job_type?: string
  publication_date?: string
  candidate_required_location?: string
  salary?: string
  description?: string
  company_logo_url?: string
}

export interface RemotiveResponse {
  "job-count"?: number
  "total-job-count"?: number
  jobs?: RemotiveJob[]
}

export interface JobResult {
  id: string
  site: "remotive"
  title: string
  company: string | null
  location: string | null
  type: string | null
  salary: string | null
  url: string
  apply_url: string
  date: string | null
  description: string | null
  category: string | null
  tags: string[]
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/**
 * Fetch Remotive jobs API with exponential backoff on 429/5xx.
 */
export async function apiGet(params: Record<string, string | number> = {}): Promise<RemotiveResponse> {
  const query = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      query.set(k, String(v))
    }
  }
  const qStr = query.toString()
  const url = qStr ? `${apiUrl()}?${qStr}` : apiUrl()

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
        `could not reach the Remotive API at ${apiUrl()} (${e instanceof Error ? e.message : String(e)})`,
      )
    }

    if (response.status === 429 || response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Remotive API request failed: ${response.status} ${response.statusText}`)
      }
      await sleep(delay + Math.floor(Math.random() * 500))
      delay = Math.min(delay * 2, 8000)
      continue
    }

    if (response.status === 404) {
      throw new Error(`Remotive API endpoint not found: 404 ${response.statusText}`)
    }

    if (!response.ok) {
      throw new Error(`Remotive API request failed: ${response.status} ${response.statusText}`)
    }

    const data = (await response.json().catch(() => null)) as RemotiveResponse | null
    if (!data) {
      throw new Error("Remotive API returned unparseable JSON")
    }
    return data
  }
  throw new Error("Remotive API request failed after retries")
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

export function extractId(input: string): string | null {
  const trimmed = input.trim()
  // Numeric string directly
  if (/^\d+$/.test(trimmed)) return trimmed

  // In URL: /remote-jobs/.../id or /job/2069746/
  const m = trimmed.match(/\/(\d{5,})(?:[\/?#]|$)/) || trimmed.match(/job[s]?\/.*?-(\d{5,})(?:[\/?#]|$)/)
  if (m) return m[1]

  const numMatch = trimmed.match(/\b(\d{5,})\b/)
  if (numMatch) return numMatch[1]

  return null
}

export function toResult(job: RemotiveJob): JobResult {
  const id = String(job.id)
  const location = job.candidate_required_location?.trim() || "Worldwide / Remote"
  const date = job.publication_date ? job.publication_date.slice(0, 10) : null

  return {
    id,
    site: "remotive",
    title: decodeHtmlEntities(job.title || "(untitled)"),
    company: job.company_name ? decodeHtmlEntities(job.company_name) : null,
    location,
    type: job.job_type ? job.job_type.replace(/_/g, " ") : null,
    salary: job.salary?.trim() || null,
    url: job.url,
    apply_url: job.url,
    date,
    description: cleanHtml(job.description),
    category: job.category || null,
    tags: job.tags || [],
  }
}
