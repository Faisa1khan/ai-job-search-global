# Himalayas API Reference

The endpoints, query parameters, and response shapes for the Himalayas remote job board.
This file documents the API contract and parsing details for future maintenance.

## Endpoint

- **Base URL:** `https://himalayas.app/jobs/api`
- **Method:** `GET`
- **Authentication:** None (public JSON API, keyless)
- **Status:** Verified live (HTTP 200)

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | integer | Number of jobs per page. Himalayas caps this server-side at 20 per request. Default 20. |
| `offset` | integer | Pagination offset (0-indexed). `offset = (page - 1) * limit`. |

Note: The public API returns an array of jobs with full fields, including complete HTML descriptions. Keyword and category filtering are performed client-side to ensure robust matching across titles, companies, excerpts, categories, and descriptions.

## Response Structure

```jsonc
{
  "comments": "...",
  "jobs": [
    {
      "title": "Law Assessment Expert - Fully Remote | Upto $105/hr",
      "excerpt": "About the jobMercor connects elite creative and technical talent with leading AI research labs.",
      "companyName": "mercor",
      "companySlug": "mercor",
      "companyLogo": "https://cdn-images.himalayas.app/...",
      "employmentType": "Full Time",
      "minSalary": 83,
      "maxSalary": 105,
      "salaryPeriod": "hourly",
      "seniority": ["Senior"],
      "currency": "USD",
      "locationRestrictions": ["United Kingdom"],
      "timezoneRestrictions": [0],
      "categories": ["Legal-Assessment-Specialist", "Assessment-Development"],
      "parentCategories": [],
      "description": "<h3>About the job</h3><p>...</p>",
      "pubDate": 1789383447,
      "expiryDate": 1794567446,
      "applicationLink": "https://himalayas.app/companies/mercor/jobs/law-assessment-expert-fully-remote-upto-105-hr-7927796087",
      "guid": "https://himalayas.app/companies/mercor/jobs/law-assessment-expert-fully-remote-upto-105-hr-7927796087"
    }
  ],
  "limit": 20,
  "offset": 0,
  "totalCount": 105575,
  "updatedAt": 1789383450
}
```

## Normalization Mapping

| Contract Field | Source Field | Processing |
|----------------|--------------|------------|
| `id` | `applicationLink` / `guid` | Last segment of path / job slug |
| `site` | `"himalayas"` | Fixed string |
| `title` | `title` | Decoded string |
| `company` | `companyName` | Decoded string |
| `location` | `locationRestrictions` | Joined comma list, or `"Worldwide / Remote"` if empty |
| `type` | `employmentType` | Employment classification (Full Time, Contractor, etc.) |
| `salary` | `minSalary`, `maxSalary`, `currency`, `salaryPeriod` | Formatted string (e.g. `USD 83–105 hourly`) |
| `url` | `applicationLink` | Direct Himalayas job URL |
| `apply_url` | `applicationLink` | Apply link |
| `date` | `pubDate` | Converted from Unix seconds to `YYYY-MM-DD` |
| `description` | `description` | HTML stripped and formatted to clean readable prose |
| `seniority` | `seniority` | First seniority tag or joined list |
| `categories` | `categories` | String array |
