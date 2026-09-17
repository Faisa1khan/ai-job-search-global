---
name: waas-search
description: >-
  Use this skill whenever the user wants to search jobs on Y Combinator Work at a Startup (workatastartup.com), find YC-backed startup jobs, look up startup job openings, or inspect a specific YC job listing. Invoke for engineering, AI, frontend, backend, fullstack, design, product, and startup roles across Y Combinator batches. Triggers on: work at a startup, workatastartup, waas, YC jobs, Y Combinator jobs, YC startups hiring, find startup jobs, search Y Combinator, look up YC job.
---

# Work at a Startup (Y Combinator) Search Skill

Search live job listings across funded startups on Y Combinator's Work at a Startup
(`workatastartup.com`). No authentication, no API key, and **zero runtime dependencies** —
runs directly with `bun`.

## ⚠️ Personal use only

This reads public pages on Y Combinator's Work at a Startup platform. Keep volume low,
use it solely for personal job search, and do not use it for commercial aggregation or
bulk scraping. Run it on your own responsibility.

> **Note on Applying vs. Searching:** Searching jobs and retrieving full listing details
> are completely public and require no authentication or API keys. Applying to a position
> redirects to Y Combinator single sign-on (`account.ycombinator.com`), which requires an
> authenticated user profile.

## When to use this skill

- Search for open startup positions across YC portfolio companies
- Filter by keywords (`--query` / `-q`), remote eligibility (`--remote`), and limit (`--limit` / `-n`)
- Inspect startup metadata including YC batch (e.g. `W16`, `S21`, `W26`), compensation/salary range, and role category
- Retrieve comprehensive job descriptions, tech stacks, and team profiles using `detail <id|url>`

## Commands

### Search job listings

```bash
bun run .agents/skills/waas-search/cli/src/cli.ts search [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — keyword search across title, company name, and role category.
- `--remote` — boolean flag; filters results to roles offering remote work (`remote: true`).
- `--limit <n>` / `-n <n>` — client-side cap on the number of results emitted (e.g. `--limit 8`).
- `--format json|table|plain` — output format (default: `json`).

### Fetch full job detail

```bash
bun run .agents/skills/waas-search/cli/src/cli.ts detail <id|url> [--format json|plain]
```

`id` is the numeric listing ID from search results (e.g. `67196` or `13302`). You may also
pass the full posting URL (`https://www.workatastartup.com/jobs/67196`).

Returns the full posting description, tech stack, hiring details, compensation and equity ranges,
visa sponsorship info, required experience, skills, and the YC application URL.

## Usage examples

```bash
# Search remote frontend engineering roles, table format, limit 8
bun run .agents/skills/waas-search/cli/src/cli.ts search --query "frontend engineer" --remote --limit 8 --format table

# Search full stack roles across all startups in JSON format
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "full stack" --limit 10 --format json

# Search AI or machine learning roles in plain text format
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "machine learning" --remote --format plain

# View all featured remote startup jobs
bun run .agents/skills/waas-search/cli/src/cli.ts search --remote --limit 15 --format table

# Inspect full details for listing 67196 in plain text format
bun run .agents/skills/waas-search/cli/src/cli.ts detail 67196 --format plain

# Inspect full details by URL in JSON format
bun run .agents/skills/waas-search/cli/src/cli.ts detail https://www.workatastartup.com/jobs/13302 --format json
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic consumption, deduplication, passing IDs to `detail` |
| `table` | Quick human scanning with ID, title, company, batch, location, remote status, category, salary |
| `plain` | Reading complete posting descriptions and company overviews |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and exit with code `1`.

## Notes

- Search hits public server-rendered pages and YC's public search API endpoint without credentials.
- Remote status is parsed from the location attribute (`location` containing "Remote").
- Batch indicates the YC cohort (e.g. `S14`, `W16`, `W23`, `P26`).
- Zero external runtime dependencies — runs on standard `bun`.
