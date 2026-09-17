# Search Queries for Job Scraper (India & Global Remote)

## Installed Portal CLIs (Primary for `/scrape`)

`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first. Installed CLIs include `linkedin-search`, `freehire-search`, `himalayas-search`, `remotive-search`, `ats-search` (direct Greenhouse, Lever, Ashby ATS company watchlist), and `waas-search` (Y Combinator Work at a Startup).

The `site:` query templates in this file are the **search_web fallback** — for portals without a CLI (Naukri, Instahyre, Cutshort, Wellfound, WeWorkRemotely, RemoteOK), company career pages, or when a CLI fails.

---

## Target Scope & Geographic Reach

### Target Work Arrangements
1. **India-Wide Remote:** Roles across India offering 100% remote work.
2. **Local / Remote (Hybrid / Onsite):** San Francisco, Noida, Local / Remote with hybrid or onsite flexibility.
3. **Remote Worldwide / Work from Anywhere:** Global remote companies hiring globally (e.g. Gitlab, Automattic, Supabase, Vercel, PostHog, Remote.com).
4. **Remote APAC:** Singapore, Australia/NZ, Japan, Southeast Asia remote roles hiring across APAC/India timezones.
5. **Remote Europe & UK:** EMEA, UK, EU remote roles open to global contractors / EOR hiring with India time overlap.
6. **Remote US & Canada:** US/North American tech companies hiring global contractors or via EOR (Deel, Oyster, Remote.com) in India.

### Role Priorities
- **Priority 1:** Senior Frontend Engineer / Senior React Developer / Senior Next.js Developer
- **Priority 2:** AI Frontend Engineer / AI-Enabled Frontend / Frontend Engineer (LLM & Agents)
- **Priority 3:** Product Engineer (Frontend-leaning / Next.js / TypeScript)
- **Priority 4:** Senior Web / UI Platform Engineer (Enterprise SaaS, Design Systems, Performance)

---

## Global Remote Evaluation & Parsing Rules

For **every global remote opportunity**, evaluate and classify parameters according to the strict 4-tier taxonomy:

### India Eligibility Classification Standards
| Confidence Level | Exact Criteria |
|---|---|
| **`CONFIRMED`** | • Posting explicitly states worldwide / global / India hiring allowed, OR<br>• Company employment policy explicitly confirms hiring in India. |
| **`LIKELY`** | • Strong verifiable evidence of India hiring exists (e.g. established Indian engineering hubs), but posting is not explicit. |
| **`UNCLEAR`** | • Posting says "Remote" or "Worldwide" without clear country eligibility bounds. |
| **`EXCLUDED`** | • Explicit US/EU/local country residency, citizenship, work authorization, or incompatible timezone requirements. |

> **Strict Rule:** NEVER upgrade `LIKELY` or `UNCLEAR` to `CONFIRMED` based solely on:
> 1. ATS platform (Greenhouse, Ashby, Lever)
> 2. Deel / Remote.com mentions
> 3. LinkedIn employee location
> 4. Generic company reputation
> 5. Inferred EOR availability
>
> In ranking reports, **show India Eligibility confidence separately from the Fit Score**.

| Parameter | Evaluation Criteria |
|---|---|
| **Country Restrictions** | Note specific country or state exclusions stated in the posting. |
| **Timezone Requirements** | Identify required working hours / overlap (e.g. UTC, EST/PST overlap, CET +/- 3h, APAC, IST). |
| **Employment Model** | Identify engagement model if stated: Full-time via EOR (Deel/Oyster/Remote), direct contractor (B2B/W8-BEN), or direct Indian subsidiary entity. |
| **Salary & Currency** | Extract compensation range and currency if available (USD, EUR, GBP, CAD, AUD, INR). |
| **No Compensation Filter Rule** | **NEVER exclude or downrank a role simply because compensation is not listed.** (Treat missing salary as standard industry practice). |

---

## CLI Execution Matrices for `/scrape`

### 1. `linkedin-search` CLI Commands

```bash
# Global Remote — Senior Frontend / React / TypeScript
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Frontend Engineer" -l "Remote" --remote remote --jobage 14 --limit 25 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior React Developer" -l "Remote" --remote remote --jobage 14 --limit 25 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Next.js Developer" -l "Remote" --remote remote --jobage 14 --limit 25 --format json

# Global Remote — AI Frontend & Product Engineering
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "AI Frontend Engineer" -l "Remote" --remote remote --jobage 14 --limit 25 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Product Engineer React" -l "Remote" --remote remote --jobage 14 --limit 25 --format json

# India-Wide Remote & Local Hybrid (Local / Remote)
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Frontend Engineer React" -l "India" --remote remote --jobage 14 --limit 25 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Frontend Engineer" -l "Remote" --jobage 14 --limit 25 --format json
bun run .agents/skills/linkedin-search/cli/src/cli.ts search -q "Senior Frontend Engineer" -l "Noida, Uttar Pradesh, India" --jobage 14 --limit 25 --format json
```

### 2. `freehire-search` CLI Commands

```bash
# Global & Multi-Region Tech Aggregator Searches
bun run .agents/skills/freehire-search/cli/src/cli.ts search -q "Senior Frontend Engineer" --region global,apac,eu,us --remote remote --category frontend,fullstack --seniority senior,lead --jobage 14 --limit 25 --format json
bun run .agents/skills/freehire-search/cli/src/cli.ts search -q "React TypeScript" --region global,eu,us --remote remote --seniority senior,lead,staff --jobage 14 --limit 25 --format json
bun run .agents/skills/freehire-search/cli/src/cli.ts search -q "Next.js" --region global,apac,eu,us --remote remote --category frontend,fullstack --jobage 14 --limit 25 --format json
bun run .agents/skills/freehire-search/cli/src/cli.ts search -q "AI Frontend" --region global,eu,us --remote remote --jobage 14 --limit 25 --format json
```

### 3. Remote-Tech Aggregators (`himalayas-search` & `remotive-search`) CLI Commands

```bash
# Himalayas — Senior Frontend / React / TypeScript / AI Roles
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "Frontend" -s senior -j 14 --limit 20 --format json
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "React" -j 14 --limit 20 --format json
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "Next.js" -j 14 --limit 20 --format json
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "AI" -s senior -j 14 --limit 20 --format json

# Remotive — Software Development Category Filtered
bun run .agents/skills/remotive-search/cli/src/cli.ts search -q "Frontend" -c "software-dev" -j 14 --limit 20 --format json
bun run .agents/skills/remotive-search/cli/src/cli.ts search -q "React" -c "software-dev" -j 14 --limit 20 --format json
bun run .agents/skills/remotive-search/cli/src/cli.ts search -q "TypeScript" -c "software-dev" -j 14 --limit 20 --format json
bun run .agents/skills/remotive-search/cli/src/cli.ts search -q "Next.js" -c "software-dev" -j 14 --limit 20 --format json
```

### 4. Company ATS Watchlist (`ats-search`) CLI Commands

```bash
# Watchlist-wide keyword searches (Greenhouse, Lever, Ashby)
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "Frontend" -j 14 --limit 25 --format json
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "React" -j 14 --limit 25 --format json
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "TypeScript" -j 14 --limit 25 --format json
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "Next.js" -j 14 --limit 25 --format json
bun run .agents/skills/ats-search/cli/src/cli.ts search -q "AI" -j 14 --limit 25 --format json

# Targeted ATS provider searches
bun run .agents/skills/ats-search/cli/src/cli.ts search -p greenhouse -q "Frontend" --limit 20 --format json
bun run .agents/skills/ats-search/cli/src/cli.ts search -p ashby -q "Frontend" --limit 20 --format json
bun run .agents/skills/ats-search/cli/src/cli.ts search -p lever -q "Frontend" --limit 20 --format json
```

### 5. `waas-search` (Y Combinator Work at a Startup) CLI Commands

```bash
# Global Remote & YC Startup Searches (Frontend, React, Fullstack, AI)
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "Frontend" --remote --limit 20 --format json
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "React" --remote --limit 20 --format json
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "Next.js" --remote --limit 20 --format json
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "Full stack" --remote --limit 20 --format json
bun run .agents/skills/waas-search/cli/src/cli.ts search -q "AI" --remote --limit 20 --format json
```

---

## search_web Fallback Queries

For portals without a dedicated CLI (Naukri, Instahyre, Wellfound, WeWorkRemotely, RemoteOK) or when a CLI fails:

### Priority 1: Senior Frontend Engineering (Global Remote & India)
```
site:weworkremotely.com "Senior Frontend" ("React" OR "TypeScript")
site:remoteok.com "Senior Frontend" ("React" OR "Next.js")
site:wellfound.com/jobs "Senior Frontend Engineer" React Remote
site:linkedin.com/jobs "Senior Frontend Engineer" ("React" OR "TypeScript") ("Worldwide" OR "Remote Worldwide" OR "Work from Anywhere")
site:linkedin.com/jobs "Senior Frontend Engineer" ("React" OR "TypeScript") "San Francisco" OR "Local / Remote" OR "Remote"
site:naukri.com "Senior Frontend Developer" React TypeScript San Francisco OR Noida OR Remote
site:instahyre.com "Senior Frontend Engineer" React TypeScript Remote OR San Francisco
site:workatastartup.com/jobs "Frontend Engineer" Remote
```

### Priority 2: AI Frontend & Agentic Engineering (Global Remote)
```
site:weworkremotely.com ("AI Frontend" OR "LLM" OR "AI Engineer") React
site:wellfound.com/jobs "Frontend Engineer" ("AI" OR "Agents" OR "LLM") ("React" OR "TypeScript") Remote
site:linkedin.com/jobs "AI Frontend Engineer" ("React" OR "TypeScript") ("Remote" OR "Worldwide")
site:linkedin.com/jobs "Software Engineer" ("Model Context Protocol" OR "MCP" OR "Agentic") TypeScript Remote
```

### Priority 3: Product Engineer & Composable Web Architecture (Global Remote)
```
site:weworkremotely.com "Product Engineer" ("React" OR "Next.js")
site:wellfound.com/jobs "Product Engineer" ("Next.js" OR "React") Remote
site:linkedin.com/jobs "Product Engineer" ("Next.js" OR "React 19") ("Remote" OR "Worldwide")
site:linkedin.com/jobs "Frontend Engineer" ("SaaS" OR "Multi-tenant") ("React" OR "TypeScript") ("Worldwide" OR "Remote")
```

---

## Date & Recency Filter

- Only include jobs posted within the **last 14 days**, or with an active application deadline that has not yet passed.
- If posting date is not explicitly visible, include and flag as `"date unknown"`.
