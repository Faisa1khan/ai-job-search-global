# ats-cli

Unified CLI for querying direct company ATS job boards (Greenhouse, Lever, Ashby) defined in `tools/ats_watchlist.json`.

## Commands

```bash
bun run src/cli.ts search [flags]
bun run src/cli.ts detail <id|url> [--format json|plain]
```

## Features

- Multi-provider support: Greenhouse, Lever, Ashby
- Direct, unauthenticated API fetching
- Normalized canonical job schema
- Watchlist configuration in `tools/ats_watchlist.json`
