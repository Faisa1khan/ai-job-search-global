---
name: remotive-search
description: >-
  Search remote tech jobs on Remotive (remotive.com). Covers software development, frontend, backend, fullstack, AI, DevOps, data, product, QA, and tech roles worldwide. Triggers on: remotive, remotive jobs, remotive remote, remote software jobs on remotive.
---

# Remotive Search Skill

Search remote tech job listings from Remotive's public API (`https://remotive.com/api/remote-jobs`).
Free, keyless, and zero runtime dependencies — runs directly with `bun`.

## When to use this skill

- Search for remote software development, frontend, backend, AI, and fullstack positions
- Filter by keywords (`--query` / `-q`), category (`--category`), recency (`--jobage`), or location
- Retrieve full descriptions and salary ranges for active remote listings

## Commands

### Search job listings

```bash
bun run .agents/skills/remotive-search/cli/src/cli.ts search [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — keyword search across title, tags, description, and company name.
- `--category <cat>` — category filter (e.g. `software-development`, `data`, `product`, `qa`).
- `--jobage <days>` — filter postings published within the last N days.
- `--limit <n>` / `-n <n>` — cap results emitted (default: 25).
- `--location <text>` / `-l <text>` — candidate required location filter (e.g. `Worldwide`, `USA`).
- `--format json|table|plain` — output format (default: `json`).

### Fetch full job detail

```bash
bun run .agents/skills/remotive-search/cli/src/cli.ts detail <id|url> [--format json|plain]
```

`id` is the numeric job ID from `search` results (e.g. `2069746`), or the full Remotive job URL.

## Usage examples

```bash
# Search for software development roles
bun run .agents/skills/remotive-search/cli/src/cli.ts search --category "software-development" --format table

# Search for React or fullstack positions
bun run .agents/skills/remotive-search/cli/src/cli.ts search -q "fullstack" --format table

# Search for roles posted in the last 14 days
bun run .agents/skills/remotive-search/cli/src/cli.ts search -q "engineer" --jobage 14 --format json

# Fetch full details of a specific job
bun run .agents/skills/remotive-search/cli/src/cli.ts detail 2069746 --format plain
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic consumption by `/scrape` and `/rank` |
| `table` | Quick human-readable summary |
| `plain` | Inspecting a single job's full description |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and exit with code `1`.
