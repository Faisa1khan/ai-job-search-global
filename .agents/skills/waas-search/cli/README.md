# waas-cli

TypeScript CLI for searching and inspecting job postings on Y Combinator's Work at a Startup (`workatastartup.com`). Zero runtime dependencies — runs directly with `bun`.

## Usage

```bash
# Search jobs
bun run src/cli.ts search --query "frontend engineer" --remote --limit 8 --format table

# View posting details
bun run src/cli.ts detail 67196 --format plain
```

## Features

- **Public access**: Queries public server-rendered pages and YC's search API with zero authentication or API keys.
- **Inertia.js payload parsing**: Extracts structured props from server-rendered HTML `<div data-page="...">`.
- **Robust error handling**: Exponential backoff with jitter on 429/5xx, structured JSON errors to stderr.
- **Interchangeable interface**: Complies with the repository's portal-skill contract (`search` and `detail` commands, `--format json|table|plain`).
