---
name: ats-search
description: >-
  Search direct company ATS job boards (Greenhouse, Lever, Ashby) across curated target companies defined in tools/ats_watchlist.json. Normalizes live job postings into a unified result set. Triggers on: ats search, watchlist jobs, greenhouse jobs, lever jobs, ashby jobs, company board search, search target companies.
---

# Company ATS Watchlist Skill

Search direct ATS job boards for target companies across Greenhouse, Lever, and Ashby.
Normalizes postings from multiple ATS providers into a single unified result set matching
the repo's canonical job schema.

## When to use this skill

- Query direct career boards of curated companies (e.g. Vercel, Stripe, GitLab, Notion, Supabase, Meesho, Atlan)
- Search across Greenhouse, Lever, and Ashby in a single query
- Find high-priority roles matching engineering, frontend, React, Next.js, and AI keywords
- Fetch complete ATS job descriptions and apply links without intermediate scraping

## Commands

### Search watchlist job listings

```bash
bun run .agents/skills/ats-search/cli/src/cli.ts search [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — keyword filter across titles and descriptions (case-insensitive). Defaults to engineering/frontend/AI roles.
- `--company <name|slug>` — restrict search to a single company from the watchlist.
- `--provider <greenhouse|lever|ashby>` — restrict search to a specific ATS platform.
- `--watchlist <path>` — path to custom watchlist JSON (default: `tools/ats_watchlist.json`).
- `--limit <n>` / `-n <n>` — cap total results emitted (default: 25).
- `--jobage <days>` — filter postings within the last N days where dates are provided.
- `--format json|table|plain` — output format (default: `json`).

### Fetch full job detail

```bash
bun run .agents/skills/ats-search/cli/src/cli.ts detail <id|url> [--format json|plain]
```

`id` can be:
- Canonical ATS composite ID: `<provider>:<slug>:<job_id>` (e.g. `greenhouse:vercel:6136160004`, `ashby:notion:1fc309c8...`)
- Direct ATS job posting URL (e.g. `https://boards.greenhouse.io/vercel/jobs/6136160004`, `https://jobs.lever.co/...`, `https://jobs.ashbyhq.com/...`)

## Usage examples

```bash
# Search target companies for frontend/React positions
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "frontend" --format table

# Search for AI or agentic roles across all watchlist companies
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "AI" --format table

# Search Notion's Ashby board specifically
bun run .agents/skills/ats-search/cli/src/cli.ts search --company notion --format table

# Inspect a specific ATS job posting
bun run .agents/skills/ats-search/cli/src/cli.ts detail "greenhouse:vercel:6136160004" --format plain
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic consumption by `/scrape` and `/rank` |
| `table` | Quick human-readable summary |
| `plain` | Reading a single job's full description |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and exit with code `1`.
