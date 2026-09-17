#!/usr/bin/env bun
// Self-contained CLI for searching jobs on Y Combinator Work at a Startup (workatastartup.com).
// No external framework, runs anywhere bun is available with zero runtime dependencies.
//
// Personal use only. Keep volume low, use solely for personal job search, and do not use
// commercially or for bulk data collection. Run on your own responsibility.

import { runSearch, type SearchOpts } from "./commands/search.js"
import { runDetail, type DetailOpts } from "./commands/detail.js"

interface Flags {
  _: string[]
  [k: string]: string | boolean | string[]
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = { _: [] }
  const alias: Record<string, string> = { q: "query", n: "limit", h: "help" }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith("--") || (a.startsWith("-") && !/^-\d/.test(a))) {
      const rawKey = a.replace(/^-+/, "")
      const key = alias[rawKey] ?? rawKey
      const next = argv[i + 1]

      if (key === "remote") {
        if (next === "true") {
          flags.remote = true
          i++
        } else if (next === "false") {
          flags.remote = false
          i++
        } else {
          flags.remote = true
        }
        continue
      }

      const isNextFlag = next !== undefined && next.startsWith("-") && !/^-\d/.test(next)
      if (next === undefined || isNextFlag) {
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

const HELP = `waas-cli — search jobs on Y Combinator Work at a Startup (workatastartup.com)

USAGE
  bun run src/cli.ts search [flags]
  bun run src/cli.ts detail <id|url> [--format json|plain]

SEARCH FLAGS
  --query, -q <text>      Keywords (title, role category, or company).
  --remote                Boolean flag; filter to remote opportunities.
  --limit, -n <n>         Cap total results emitted (client-side).
  --format <fmt>          json (default) | table | plain.

EXAMPLES
  bun run src/cli.ts search --query "frontend engineer" --remote --limit 8 --format table
  bun run src/cli.ts search -q "machine learning" --remote --format table
  bun run src/cli.ts search -q "full stack" --limit 10 --format json
  bun run src/cli.ts search --remote --limit 15 --format table
  bun run src/cli.ts detail 67196 --format plain
  bun run src/cli.ts detail https://www.workatastartup.com/jobs/13302 --format json

Personal use only — keep volume low (workatastartup.com).
Note: Applying requires a Y Combinator login, but searching and details do not.
`

const KNOWN_FLAGS: Record<string, Set<string>> = {
  search: new Set(["query", "remote", "limit", "format", "help", "h"]),
  detail: new Set(["format", "help", "h"]),
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

  const knownFlags = KNOWN_FLAGS[cmd]
  if (knownFlags) {
    for (const key of Object.keys(flags)) {
      if (key === "_" || knownFlags.has(key)) continue
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

    const parseIntFlag = (name: string, raw: string | boolean | string[]): number | null => {
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

    if (flags.limit !== undefined) {
      const v = parseIntFlag("limit", flags.limit)
      if (v === null) return 1
      flags.limit = String(v)
    }

    const opts: SearchOpts = {
      query: typeof flags.query === "string" ? flags.query : undefined,
      remote: flags.remote === true,
      limit: flags.limit ? parseInt(flags.limit as string, 10) : undefined,
      format: (["json", "table", "plain"].includes(fmt) ? fmt : "json") as SearchOpts["format"],
    }
    return runSearch(opts)
  }

  if (cmd === "detail") {
    const id = (flags._ as string[])[1]
    if (!id) {
      process.stderr.write(
        JSON.stringify({ error: "detail requires an <id|url>", code: "NO_ID" }) + "\n",
      )
      return 1
    }
    const fmt = (flags.format as string) || "json"
    const opts: DetailOpts = {
      id,
      format: (fmt === "plain" ? "plain" : "json") as DetailOpts["format"],
    }
    return runDetail(opts)
  }

  process.stderr.write(
    JSON.stringify({ error: `Unknown command "${cmd}"`, code: "BAD_CMD" }) + "\n",
  )
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
