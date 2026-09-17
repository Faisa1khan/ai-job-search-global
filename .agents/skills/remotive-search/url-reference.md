# Remotive API Reference

The endpoints, parameters, and response shapes for the Remotive remote job board.
This file documents the API contract and parsing details for future maintenance.

## Endpoint

- **Base URL:** `https://remotive.com/api/remote-jobs`
- **Method:** `GET`
- **Authentication:** None (public JSON API, keyless)
- **Status:** Verified live (HTTP 200)

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Optional category filter slug (e.g. `software-development`, `data`, `product`) |
| `search` | string | Optional search keyword parameter |
| `limit` | integer | Optional limit parameter |

Note: Remotive provides an unauthenticated feed of remote job listings. The response includes full HTML descriptions, tags, and location requirements. The CLI performs client-side keyword, category, recency, and location filtering to guarantee exact matching and limit control.

## Response Structure

```jsonc
{
  "0-legal-notice": "...",
  "00-warning": "...",
  "job-count": 16,
  "total-job-count": 16,
  "jobs": [
    {
      "id": 2069746,
      "url": "https://remotive.com/remote-jobs/software-development/...",
      "title": "Senior Fullstack Engineer",
      "company_name": "Mitre Media",
      "company_logo": "https://remotive.com/job/2069746/logo",
      "category": "Software Development",
      "tags": ["rails", "api", "ai"],
      "job_type": "full_time",
      "publication_date": "2026-09-14T09:30:00",
      "candidate_required_location": "Worldwide",
      "salary": "$160,000 - $200,000",
      "description": "<p>Job description HTML...</p>",
      "company_logo_url": "https://remotive.com/job/2069746/logo"
    }
  ]
}
```

## Normalization Mapping

| Contract Field | Source Field | Processing |
|----------------|--------------|------------|
| `id` | `id` | Stringified numeric ID |
| `site` | `"remotive"` | Fixed string |
| `title` | `title` | Decoded string |
| `company` | `company_name` | Decoded string |
| `location` | `candidate_required_location` | String, or `"Worldwide / Remote"` if empty |
| `type` | `job_type` | Job type string (e.g. full_time, contract) |
| `salary` | `salary` | Raw or formatted salary string |
| `url` | `url` | Remotive posting URL |
| `apply_url` | `url` | Remotive application URL |
| `date` | `publication_date` | Sliced to `YYYY-MM-DD` |
| `description` | `description` | HTML stripped and formatted to clean readable prose |
| `category` | `category` | Remotive category string |
| `tags` | `tags` | String array |
