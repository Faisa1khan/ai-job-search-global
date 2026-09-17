// Helpers and fetch utilities for Y Combinator Work at a Startup (waas-search)
// Endpoints are unauthenticated and public.
// Server-rendered pages provide Inertia.js data-page attributes; search queries
// query /jobs/search?q=... used by the web interface.

export const BASE_URL = "https://www.workatastartup.com"
export const JOBS_URL = "https://www.workatastartup.com/jobs"
export const SEARCH_API_URL = "https://www.workatastartup.com/jobs/search"
export const UA = "Mozilla/5.0 (compatible; waas-search-cli/1.0)"

export function writeError(error: string, code: string): void {
  process.stderr.write(JSON.stringify({ error, code }) + "\n")
}

/** Fetch HTML with exponential backoff on 429/5xx. Returns "" on 404. */
export async function htmlFetch(url: string): Promise<string> {
  const maxRetries = 6
  let delay = 500
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, {
      headers: {
        "User-Agent": UA,
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
      redirect: "follow",
      signal: AbortSignal.timeout(15000),
    })
    if (response.status === 429 || response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`)
      }
      const jitter = Math.floor(Math.random() * 500)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 8000)
      continue
    }
    if (response.status === 404) return ""
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return response.text()
  }
  throw new Error("Request failed after max retries")
}

/** Fetch JSON with exponential backoff on 429/5xx. Returns null on 404. */
export async function jsonFetch<T = unknown>(url: string): Promise<T | null> {
  const maxRetries = 6
  let delay = 500
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, {
      headers: {
        "User-Agent": UA,
        Accept: "application/json",
        "Accept-Language": "en-US,en;q=0.9",
      },
      redirect: "follow",
      signal: AbortSignal.timeout(15000),
    })
    if (response.status === 429 || response.status >= 500) {
      if (attempt === maxRetries) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`)
      }
      const jitter = Math.floor(Math.random() * 500)
      await new Promise((r) => setTimeout(r, delay + jitter))
      delay = Math.min(delay * 2, 8000)
      continue
    }
    if (response.status === 404) return null
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status} ${response.statusText}`)
    }
    return (await response.json()) as T
  }
  throw new Error("Request failed after max retries")
}

/** Unescape standard HTML entities without third-party dependencies */
export function unescapeHtml(str: string): string {
  return str
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, "/")
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(Number(dec)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
}

/** Convert raw HTML snippet into clean readable plain text with preserved paragraphs */
export function htmlToPlain(html: string | null | undefined): string {
  if (!html) return ""
  let t = html
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\s*\/p\s*>/gi, "\n\n")
    .replace(/<\s*\/div\s*>/gi, "\n\n")
    .replace(/<\s*\/li\s*>/gi, "\n")
    .replace(/<\s*li\s*>/gi, "• ")
    .replace(/<[^>]+>/g, "")
  t = unescapeHtml(t)
  const lines = t.split("\n").map((l) => l.trim())
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim()
}

/** Extract Inertia.js data-page payload from HTML */
export function parseDataPage(html: string): any {
  const match = html.match(/data-page="([^"]+)"/) || html.match(/data-page='([^']+)'/)
  if (!match) return null
  try {
    const unescaped = unescapeHtml(match[1])
    return JSON.parse(unescaped)
  } catch {
    return null
  }
}

export interface RawJob {
  id: number | string
  title: string
  jobType?: string | null
  location?: string | null
  roleType?: string | null
  salary?: string | null
  companyName?: string | null
  companySlug?: string | null
  companyBatch?: string | null
  companyOneLiner?: string | null
  companyLogoUrl?: string | null
  companyLastActiveAt?: string | null
  applyUrl?: string | null
}

export interface WaasJobCard {
  id: string
  title: string
  company: string
  batch: string | null
  location: string | null
  remote: boolean
  category: string | null
  salary: string | null
  date: string | null
  url: string
}

export interface WaasJobDetail extends WaasJobCard {
  equity: string | null
  jobType: string | null
  minExperience: string | null
  sponsorsVisa: string | null
  skills: string[]
  description: string | null
  companyDescription: string | null
  techDescription: string | null
  hiringDescription: string | null
  companyUrl: string | null
  teamSize: number | null
  applyUrl: string
}

export function mapRawToCard(raw: RawJob): WaasJobCard {
  const idStr = String(raw.id)
  const loc = raw.location || ""
  const isRemote = /\bremote\b/i.test(loc)
  return {
    id: idStr,
    title: raw.title || "",
    company: raw.companyName || "",
    batch: raw.companyBatch || null,
    location: raw.location || null,
    remote: isRemote,
    category: raw.roleType || null,
    salary: raw.salary || null,
    date: raw.companyLastActiveAt || null,
    url: `${BASE_URL}/jobs/${idStr}`,
  }
}

export interface SearchFilters {
  query?: string
  remote?: boolean
  limit?: number
}

/**
 * Fetch jobs matching filters.
 * Hits https://www.workatastartup.com/jobs?query=...&remote=true (server-rendered page)
 * and /jobs/search?q=... for full keyword search results.
 */
export async function fetchJobs(filters: SearchFilters): Promise<WaasJobCard[]> {
  const jobsMap = new Map<string, WaasJobCard>()

  // 1. Fetch server-rendered /jobs page (with query/remote query params)
  const pageParams = new URLSearchParams()
  if (filters.query && filters.query.trim()) pageParams.set("query", filters.query.trim())
  if (filters.remote) pageParams.set("remote", "true")
  const pageUrl = `${JOBS_URL}${pageParams.toString() ? `?${pageParams.toString()}` : ""}`

  try {
    const html = await htmlFetch(pageUrl)
    if (html) {
      const data = parseDataPage(html)
      const pageJobs = data?.props?.jobs
      if (Array.isArray(pageJobs)) {
        for (const j of pageJobs) {
          const card = mapRawToCard(j)
          jobsMap.set(card.id, card)
        }
      }
    }
  } catch {
    // If HTML page fetch encounters an issue, proceed to search API
  }

  // 2. If query is provided, also query /jobs/search which searches across all YC jobs
  if (filters.query && filters.query.trim()) {
    try {
      const searchUrl = `${SEARCH_API_URL}?q=${encodeURIComponent(filters.query.trim())}`
      const searchData = await jsonFetch<{ jobs?: RawJob[] }>(searchUrl)
      if (searchData?.jobs && Array.isArray(searchData.jobs)) {
        for (const j of searchData.jobs) {
          const card = mapRawToCard(j)
          jobsMap.set(card.id, card)
        }
      }
    } catch {
      // Continue with whatever jobs were found
    }
  }

  let cards = Array.from(jobsMap.values())

  // If query is provided, filter client-side to ensure query relevance
  if (filters.query && filters.query.trim()) {
    const qRaw = filters.query.trim().toLowerCase()
    const words = qRaw.split(/\s+/).filter(Boolean)
    const normQuery = qRaw.replace(/front[\s-]end/g, "frontend")

    cards = cards.filter((c) => {
      const target = `${c.title} ${c.category || ""} ${c.company}`.toLowerCase()
      const normTarget = target.replace(/front[\s-]end/g, "frontend")
      if (normTarget.includes(normQuery)) return true
      return words.every((w) => {
        const normW = w.replace(/front[\s-]end/g, "frontend")
        return normTarget.includes(normW)
      })
    })
  }

  // Filter by remote if remote flag requested
  if (filters.remote) {
    cards = cards.filter((c) => c.remote)
  }

  // Apply limit
  if (filters.limit !== undefined && filters.limit >= 0) {
    cards = cards.slice(0, filters.limit)
  }

  return cards
}

export function parseJobDetail(data: any, id: string): WaasJobDetail {
  const job = data?.props?.job || {}
  const comp = data?.props?.company || {}
  const applyUrl = data?.props?.applyUrl || `${BASE_URL}/jobs/${id}`
  const loc = job.location || comp.location || null
  const isRemote = typeof loc === "string" && /\bremote\b/i.test(loc)

  return {
    id,
    title: job.title || "",
    company: comp.name || "",
    batch: comp.batch || null,
    location: loc,
    remote: isRemote,
    category: null,
    salary: job.salaryRange || null,
    equity: job.equityRange || null,
    jobType: job.jobType || null,
    minExperience: job.minExperience || null,
    sponsorsVisa: job.sponsorsVisa || null,
    skills: Array.isArray(job.skills) ? job.skills : [],
    date: null,
    url: `${BASE_URL}/jobs/${id}`,
    description: htmlToPlain(job.descriptionHtml),
    companyDescription: htmlToPlain(comp.description),
    techDescription: htmlToPlain(comp.techDescriptionHtml),
    hiringDescription: htmlToPlain(comp.hiringDescriptionHtml),
    companyUrl: comp.url || null,
    teamSize: typeof comp.teamSize === "number" ? comp.teamSize : null,
    applyUrl,
  }
}
