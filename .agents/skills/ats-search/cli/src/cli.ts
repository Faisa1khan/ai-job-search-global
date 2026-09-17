#!/usr/bin/env bun
// ATS CLI — search direct company ATS job boards (Greenhouse, Lever, Ashby).
// Keyless, public JSON, zero external runtime dependencies.

import { runSearch, type SearchOpts } from "./commands/search.js"
import { runDetail, type DetailOpts } from "./commands/detail.js"

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

const ALIAS: Record<string, string> = {
  q: "query",
  n: "limit",
  c: "company",
  p: "provider",
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith("--") || a.startsWith("-")) {
      const name = a.replace(/^-+/, "")
      const key = ALIAS[name] ?? name
      const next = argv[i + 1]
      if (next === undefined || next.startsWith("-")) {
        flags[key] = true
      } else {
        flags[key] = next
        i++
      }
    } else {
      ;(flags._ as string[]).push(a)
    }
  }
  return flags
}

const HELP = `ats-cli — search direct company ATS job boards (Greenhouse, Lever, Ashby)

USAGE
  bun run src/cli.ts search [flags]
  bun run src/cli.ts detail <id|url> [--format json|plain]

SEARCH FLAGS
  --query, -q <text>      Keywords (title, description). Default matches engineer/frontend/react/ai.
  --company, -c <name>    Filter to a specific target company name or slug.
  --provider, -p <prov>   Filter to greenhouse | lever | ashby.
  --watchlist <path>      Custom path to watchlist JSON (default: tools/ats_watchlist.json).
  --jobage <days>         Posted within the last N days (where publication date is available).
  --limit, -n <n>         Cap total results emitted. Default: 25.
  --format <fmt>          json (default) | table | plain.

DETAIL
  <id|url>                Composite ID (provider:slug:jobId) or direct ATS job URL.

EXAMPLES
  bun run src/cli.ts search -q "frontend" --format table
  bun run src/cli.ts search --company notion --format table
  bun run src/cli.ts search --provider greenhouse --limit 10 --format table
  bun run src/cli.ts detail "greenhouse:vercel:6136160004" --format plain
`

const KNOWN_FLAGS: Record<string, Set<string>> = {
  search: new Set([
    "query",
    "company",
    "provider",
    "watchlist",
    "jobage",
    "limit",
    "format",
    "help",
    "h",
  ]),
  detail: new Set(["watchlist", "format", "help", "h"]),
}

function parseIntFlag(name: string, raw: string | boolean | string[]): number | null {
  const val = typeof raw === "string" ? Number(raw.trim()) : NaN
  if (!Number.isInteger(val) || val < 1) {
    process.stderr.write(
      JSON.stringify({
        error: `--${name} must be a whole number of at least 1, got "${raw}"`,
        code: "BAD_ARG",
      }) + "\n",
    )
    return null
  }
  return val
}

async function main(): Promise<number> {
  const argv = process.argv.slice(2)
  const flags = parseFlags(argv)
  const cmd = (flags._ as string[])[0]

  if (flags.help || flags.h) {
    process.stdout.write(HELP)
    return 0
  }

  if (!cmd) {
    process.stdout.write(HELP)
    return 1
  }

  const known = KNOWN_FLAGS[cmd]
  if (known) {
    for (const key of Object.keys(flags)) {
      if (key === "_" || known.has(key)) continue
      process.stderr.write(
        JSON.stringify({
          error: `unknown flag --${key} for '${cmd}' - flags are never silently ignored; see --help for supported flags`,
          code: "UNKNOWN_FLAG",
        }) + "\n",
      )
      return 1
    }
  }

  if (cmd === "search") {
    const fmt = (flags.format as string) || "json"

    for (const name of ["jobage", "limit"] as const) {
      if (flags[name] !== undefined) {
        const v = parseIntFlag(name, flags[name])
        if (v === null) return 1
        flags[name] = String(v)
      }
    }

    const opts: SearchOpts = {
      query: typeof flags.query === "string" ? flags.query : undefined,
      company: typeof flags.company === "string" ? flags.company : undefined,
      provider: typeof flags.provider === "string" ? flags.provider : undefined,
      watchlist: typeof flags.watchlist === "string" ? flags.watchlist : undefined,
      jobage: flags.jobage ? parseInt(flags.jobage as string, 10) : undefined,
      limit: flags.limit ? Math.max(1, parseInt(flags.limit as string, 10)) : 25,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
    }
    return runSearch(opts)
  }

  if (cmd === "detail") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(JSON.stringify({ error: "detail requires an <id|url>", code: "NO_ID" }) + "\n")
      return 1
    }
    const fmt = (flags.format as string) || "json"
    const opts: DetailOpts = {
      id,
      format: (fmt === "plain" ? "plain" : "json") as DetailOpts["format"],
      watchlist: typeof flags.watchlist === "string" ? flags.watchlist : undefined,
    }
    return runDetail(opts)
  }

  process.stderr.write(JSON.stringify({ error: `Unknown command "${cmd}"`, code: "BAD_CMD" }) + "\n")
  return 1
}

main()
  .then((code) => process.exit(code))
  .catch((e) => {
    process.stderr.write(
      JSON.stringify({
        error: e instanceof Error ? e.message : String(e),
        code: "INTERNAL_ERROR",
      }) + "\n",
    )
    process.exit(1)
  })
