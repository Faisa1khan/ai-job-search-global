# remotive-cli

Zero-dependency CLI for searching remote tech jobs on Remotive (`https://remotive.com/api/remote-jobs`).

## Commands

```bash
bun run src/cli.ts search [flags]
bun run src/cli.ts detail <id|url> [--format json|plain]
```

## Features

- Public, keyless JSON API
- Client-side keyword, category, recency, and location filtering
- Normalization into canonical job schema: `id`, `site`, `title`, `company`, `location`, `type`, `salary`, `url`, `apply_url`, `date`, `description`
