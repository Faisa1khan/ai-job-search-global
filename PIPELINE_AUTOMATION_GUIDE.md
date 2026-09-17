# End-to-End Autonomous Job Application Pipeline Guide

This document describes the fully automated recruitment engine built for **Alex Doe** in `ai-job-search-global`.

---

## 1. Pipeline Architecture

```mermaid
flowchart TD
    Trigger["Trigger: Autonomous Pipeline<br>(Manual CLI or Scheduled Cron)"] --> Scrape
    
    subgraph S1["Phase 1: Parallel Portal Scraping"]
        Scrape["Concurrent Bun Portal CLIs<br>(LinkedIn, WAAS, Freehire, Himalayas, Remotive, ATS)"]
    end
    
    subgraph S2["Phase 2: Deduplication & Scoring"]
        Scrape --> Dedupe["Deduplicate against seen_jobs.json & tracker"]
        Dedupe --> Score["5-Dimension Candidate Fit Evaluation<br>(Tech 40%, Experience 30%, Product 30%)"]
        Score --> Filter["Eligibility & Location Gate<br>(India Remote, Global Remote, Local / Remote)"]
        Filter --> Select["Select Top N Unapplied Fits (Score >= 90)"]
    end
    
    subgraph S3["Phase 3: Autonomous Package Drafting"]
        Select --> Research["Deep Company Research (company_research/<slug>.json)"]
        Research --> Archive["Archive Job Posting (documents/applications/<slug>/job_posting.md)"]
        Archive --> Resume["Generate 1-Page Resume HTML (SOT Grounded)"]
        Archive --> Cover["Generate 1-Page Cover Letter HTML (Humanizer Clean)"]
    end
    
    subgraph S4["Phase 4: Chromium PDF Rendering & 4-Gate Verification"]
        Resume --> ChromeR["Headless Chromium Compilation"]
        Cover --> ChromeC["Headless Chromium Compilation"]
        ChromeR --> V1["1. verify_pdf.py (Exact 1-Page)"]
        ChromeR --> V2["2. verify_layout.py (Density & Bottom Space <= 75pt)"]
        ChromeC --> V3["3. verify_humanizer.py (No AI Tells, Mentions Claude Code)"]
        ChromeR --> V4["4. verify_sot.py (29 ADRs, 25 Playwright, 42 OpenAPI)"]
        
        V2 -- "Minor Spacing Gap" --> AutoHeal["Auto-Healing Engine<br>(Dynamic Margin/Font Calibration)"] --> ChromeR
    end
    
    subgraph S5["Phase 5: Tracking & Audit"]
        V1 & V2 & V3 & V4 --> Record["Record in job_search_tracker.csv"]
        Record --> Output["Generate Executive Run Report & File Links"]
    end
```

---

## 2. CLI Usage & Commands

The unified autonomous engine is implemented in [`tools/autonomous_job_pipeline.py`](tools/autonomous_job_pipeline.py).

### A. Full End-to-End Pipeline (Scrape $\to$ Rank $\to$ Tailor $\to$ Compile $\to$ Verify $\to$ Record)

```bash
# Scrape all portals, pick top 5 global remote fits, and generate verified packages:
python3 tools/autonomous_job_pipeline.py --mode full --target global-remote --top 5

# Target India-wide remote and Local / Remote local hybrid:
python3 tools/autonomous_job_pipeline.py --mode full --target india-remote --top 5

# Target all remote & regional opportunities:
python3 tools/autonomous_job_pipeline.py --mode full --target all --top 5
```

### B. Fast Batch Drafting on Cached / Scraped Postings

```bash
# Draft packages for the top 5 highest-scoring unapplied jobs without re-scraping:
python3 tools/autonomous_job_pipeline.py --mode apply-batch --no-scrape --top 5
```

### C. Portal Scraping Only

```bash
# Run broad scrape across all 6 portal CLIs and update seen_jobs.json:
python3 tools/autonomous_job_pipeline.py --mode scrape-only --days 14
```

### D. Fit Ranking & Shortlisting Only

```bash
# View JSON output of top 10 unapplied candidates sorted by fit score:
python3 tools/autonomous_job_pipeline.py --mode rank-only --top 10
```

---

## 3. Unattended Scheduling (Cron & Antigravity Native)

### Option 1: Native Antigravity Schedule (Recommended)
You can trigger recurring background runs directly inside Antigravity by using the `/schedule` command:

```text
/schedule cron="0 9 * * 1-5" prompt="Run autonomous job search pipeline: python3 tools/autonomous_job_pipeline.py --mode full --target global-remote --top 3"
```

### Option 2: Linux User Crontab
To run every weekday at 9:00 AM UTC:

```bash
0 9 * * 1-5 cd this repository && /usr/bin/python3 tools/autonomous_job_pipeline.py --mode full --target global-remote --top 3 >> cron.log 2>&1
```

---

## 4. Strict Quality & Grounding Directives

Every package produced by the automated pipeline strictly satisfies all four verification criteria:
1. **1-Page Physical Geometry:** Single page with balanced density (bottom whitespace $\le 75\text{pt}$ / $\approx 9.5\%$).
2. **Humanizer & Tone Rules:** Zero banned AI words (*leverage*, *spearhead*, *align with*), zero em dashes in body prose, and natural conversational cadence.
3. **Grounding SOT (Career Source of Truth):**
   - **Project Nexus:** 29 ADRs, 25 Playwright test suites, 16 modules.
   - **Acme Corp:** 8 core HRMS modules, 42 OpenAPI endpoints, 10,000+ active enterprise users, 28 Indian states statutory compliance.
   - **Status & Notice:** 45-day notice period, NO US work authorization claim.
4. **Master Template Conformity:** Uses locked HTML/CSS structure from `cv/Resume_Master.html` and `cover_letters/Cover_Letter_Master.html`.
