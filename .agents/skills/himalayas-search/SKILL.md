---
name: himalayas-search
description: >-
  Search remote tech job listings from Himalayas (himalayas.app). Features remote software engineering, frontend, backend, fullstack, AI, DevOps, design, and product roles across global remote and regional hiring bounds. Triggers on: himalayas, himalayas jobs, remote tech jobs, remote engineering jobs, find remote jobs on himalayas.
---

# Himalayas Search Skill

Search remote tech job listings from Himalayas' public API (`https://himalayas.app/jobs/api`).
Free, keyless, and zero runtime dependencies — runs directly with `bun`.

## When to use this skill

- Search for remote software engineering, AI, frontend, and fullstack positions
- Filter by keywords (`--query` / `-q`), recency (`--jobage`), categories, or location restrictions
- Retrieve full descriptions and structured compensation for remote positions

## Commands

### Search job listings

```bash
bun run .agents/skills/himalayas-search/cli/src/cli.ts search [flags]
```

Key flags:
- `--query <text>` / `-q <text>` — keyword search across title, excerpt, categories, and description.
- `--jobage <days>` — filter postings published within the last N days.
- `--page <n>` — 1-indexed page number (default: 1).
- `--limit <n>` / `-n <n>` — cap results emitted (default: 20).
- `--category <cat>` — filter by category (e.g. `Developer`, `Frontend-Development`).
- `--location <text>` / `-l <text>` — filter by permitted location restrictions.
- `--format json|table|plain` — output format (default: `json`).

### Fetch full job detail

```bash
bun run .agents/skills/himalayas-search/cli/src/cli.ts detail <id|slug|url> [--format json|plain]
```

`id` is the slug from `search` results (e.g. `senior-full-stack-developer-net-x2f-angular-...` or numeric ID). You may also pass the full `https://himalayas.app/companies/.../jobs/...` URL.

## Usage examples

```bash
# Search for frontend engineering roles
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "frontend" --format table

# Search for React or TypeScript roles posted in the last 14 days
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "React" --jobage 14 --limit 10 --format table

# Search for AI or ML engineering positions
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "AI" --format json

# Fetch full details of a specific job
bun run .agents/skills/himalayas-search/cli/src/cli.ts detail law-assessment-expert-fully-remote-upto-105-hr-7927796087 --format plain
```

## Output formats

| Format | Best for |
|--------|----------|
| `json` | Default — programmatic consumption by `/scrape` and `/rank` |
| `table` | Quick human-readable summary |
| `plain` | Inspecting a single job's full description |

All errors are written to **stderr** as `{ "error": "...", "code": "..." }` and exit with code `1`.
