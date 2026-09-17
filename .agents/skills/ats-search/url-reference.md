# Company ATS Watchlist API Reference

The endpoints, parameters, and response schemas for querying direct ATS job boards across target companies.
Supported providers: Greenhouse, Lever, and Ashby. All endpoints are public, keyless JSON APIs.

## Supported ATS Providers & Endpoints

### 1. Greenhouse
- **Search / List Endpoint:** `GET https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true`
- **Detail Endpoint:** `GET https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs/{job_id}`
- **Authentication:** Keyless
- **Response Format:**
```jsonc
{
  "jobs": [
    {
      "id": 6136160004,
      "title": "Forward-Deployed Engineer",
      "absolute_url": "https://boards.greenhouse.io/vercel/jobs/6136160004",
      "location": { "name": "Remote - US" },
      "first_published": "2026-09-10T12:00:00Z",
      "updated_at": "2026-09-14T05:00:00Z",
      "content": "&lt;p&gt;Job description HTML...&lt;/p&gt;"
    }
  ]
}
```

### 2. Lever
- **Search / List Endpoint:** `GET https://api.lever.co/v0/postings/{company_slug}?limit={limit}`
- **Detail Endpoint:** `GET https://api.lever.co/v0/postings/{company_slug}/{posting_id}`
- **Authentication:** Keyless
- **Response Format:**
```jsonc
[
  {
    "id": "7d9af9b5-c1c7-48ec-bbb5-9b25e49f6596",
    "text": "Software Development Engineer III - Backend",
    "hostedUrl": "https://jobs.lever.co/meesho/7d9af9b5-c1c7-48ec-bbb5-9b25e49f6596",
    "applyUrl": "https://jobs.lever.co/meesho/7d9af9b5-c1c7-48ec-bbb5-9b25e49f6596/apply",
    "categories": { "location": "Bangalore, Karnataka", "team": "Engineering" },
    "workplaceType": "hybrid",
    "createdAt": 1789380000000,
    "descriptionPlain": "Job description text..."
  }
]
```

### 3. Ashby
- **Search / List Endpoint:** `GET https://api.ashbyhq.com/posting-api/job-board/{company_slug}?includeCompensation=true`
- **Detail Endpoint:** Retrieved from the board endpoint by `id` matching.
- **Authentication:** Keyless
- **Response Format:**
```jsonc
{
  "apiVersion": "1.0",
  "jobs": [
    {
      "id": "1fc309c8-da20-4ff2-84c7-8b863ece2b0a",
      "title": "Software Engineer, Developer Platform",
      "jobUrl": "https://jobs.ashbyhq.com/notion/1fc309c8-da20-4ff2-84c7-8b863ece2b0a",
      "applyUrl": "https://jobs.ashbyhq.com/notion/1fc309c8-da20-4ff2-84c7-8b863ece2b0a/application",
      "location": "San Francisco, CA or Remote (US)",
      "isRemote": true,
      "publishedAt": "2026-09-12T16:00:00.000Z",
      "compensation": {
        "compensationTierSummary": "$180,000—$240,000 USD"
      },
      "descriptionPlain": "Job description text...",
      "descriptionHtml": "<p>Job description HTML...</p>"
    }
  ]
}
```

## Watchlist Configuration (`tools/ats_watchlist.json`)

```jsonc
[
  {
    "company": "Vercel",
    "provider": "greenhouse",
    "slug": "vercel",
    "keywords": ["frontend", "engineer", "react", "next.js", "typescript", "ai"]
  },
  {
    "company": "Notion",
    "provider": "ashby",
    "slug": "notion",
    "keywords": ["frontend", "engineer", "react", "product"]
  },
  {
    "company": "Meesho",
    "provider": "lever",
    "slug": "meesho",
    "keywords": ["engineer", "software", "backend", "ai"]
  }
]
```
