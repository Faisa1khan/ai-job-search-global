# Work at a Startup (YC) URL Reference

Public, unauthenticated endpoints on Y Combinator's Work at a Startup (`workatastartup.com`) used by this skill. No API key or authentication is required for search and detail lookups.

> **Personal use only** — keep volume low and do not use for bulk crawling or commercial aggregation. Applying to jobs requires single sign-on through a Y Combinator account, but search and detail viewing are public.

## Endpoints

### 1. Server-Rendered Jobs Directory (HTML with Inertia.js props)

```
GET https://www.workatastartup.com/jobs?query=<text>&remote=true
```

Query parameters:

| Param | Type | Description | Example |
|---|---|---|---|
| `query` | string | Keyword query for title, company, or role | `frontend engineer` |
| `remote` | boolean | Remote filter parameter | `true` |
| `role` | string | Broad role filter | `software-engineer`, `designer` |

Returns server-rendered HTML containing an Inertia.js root element:
```html
<div data-page="{&quot;component&quot;:&quot;jobs/public/pages/JobsPage&quot;,&quot;props&quot;:{&quot;jobs&quot;:[...]},...}"></div>
```
The CLI parses the HTML-entity-encoded JSON in `data-page` directly, bypassing client-side JavaScript execution.

### 2. Search API (JSON)

```
GET https://www.workatastartup.com/jobs/search?q=<query>
```

Query parameters:

| Param | Type | Description | Example |
|---|---|---|---|
| `q` | string | Free-text search term | `frontend engineer` |

Returns JSON payload:
```json
{
  "jobs": [
    {
      "id": 67196,
      "title": "Frontend Engineer",
      "jobType": "Fulltime",
      "location": "Remote (US)",
      "roleType": "Frontend",
      "salary": "$80K - $250K",
      "companyName": "Chima",
      "companySlug": "chima",
      "companyBatch": "W23",
      "companyOneLiner": "AI agents for financial services",
      "companyLogoUrl": "https://...",
      "companyLastActiveAt": "3 days ago",
      "applyUrl": "https://account.ycombinator.com/authenticate?continue=..."
    }
  ]
}
```

### 3. Job Detail (HTML with Inertia.js props)

```
GET https://www.workatastartup.com/jobs/<id>
```

Accepts numeric job IDs (e.g. `13302`, `67196`). Returns an HTML document with component `jobs/public/pages/JobDetailPage`.
Props extracted:
- `props.job`: `id`, `title`, `salaryRange`, `equityRange`, `location`, `jobType`, `sponsorsVisa`, `minExperience`, `skills`, `descriptionHtml`
- `props.company`: `name`, `slug`, `batch`, `description`, `hiringDescriptionHtml`, `techDescriptionHtml`, `logoUrl`, `url`, `location`, `teamSize`, `industry`, `founders`
- `props.applyUrl`: Direct YC SSO application link

## Data Model & Field Mapping

| Output Field | Source in Search | Source in Detail | Notes |
|---|---|---|---|
| `id` | `id` | `job.id` | Numeric string |
| `title` | `title` | `job.title` | Full job title |
| `company` | `companyName` | `company.name` | Company name |
| `batch` | `companyBatch` | `company.batch` | YC batch code (e.g. `W16`, `S21`, `W26`) |
| `location` | `location` | `job.location` | Location text, may include multiple regions |
| `remote` | `/\bremote\b/i.test(location)` | `/\bremote\b/i.test(location)` | Boolean flag |
| `category` | `roleType` | N/A | Broad role category (Frontend, Full stack, Backend, ML, Design) |
| `salary` | `salary` | `job.salaryRange` | Formatted salary range or null |
| `equity` | N/A | `job.equityRange` | Equity range string (e.g. `0.05% - 0.15%`) |
| `date` | `companyLastActiveAt` | null | Recency indicator (e.g. "3 days ago") |
| `url` | `https://www.workatastartup.com/jobs/<id>` | Same | Canonical posting URL |

## Access & Policy Notes

- **Authentication**: None required for searching and viewing job postings.
- **Applying**: Applying redirects to `https://account.ycombinator.com/authenticate` which requires a user login.
- **Robots.txt**: `User-Agent: * Disallow: ` (no paths disallowed).
- **Rate Limits**: Retries on 429/5xx with exponential backoff and jitter. Keep requests low-volume for personal search use.
