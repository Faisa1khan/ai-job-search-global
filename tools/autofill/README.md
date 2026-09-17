# AI Job Application Auto-Filler (Tampermonkey / Violentmonkey)

An ultra-reliable, SOT-grounded browser userscript that instantly auto-fills job application forms with verified candidate data from [`CAREER_SOURCE_OF_TRUTH.md`](file://CAREER_SOURCE_OF_TRUTH.md).

---

## 1. Quick Installation (10 Seconds)

1. Install the **Tampermonkey** or **Violentmonkey** extension in your browser:
   * [Chrome Web Store](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo) / [Brave](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo) / [Firefox](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)
2. Open Tampermonkey dashboard $\to$ **Create a new script** (`+` icon).
3. Select all and paste the complete content of [`tools/autofill/autofill.user.js`](tools/autofill/autofill.user.js).
4. Save (`Ctrl+S` or `Cmd+S`).

---

## 2. Supported Application Portals

Works out-of-the-box across all major job portals and Applicant Tracking Systems:

* ✅ **Workable** (`apply.workable.com/*`)
* ✅ **LinkedIn Easy Apply** (`linkedin.com/*`)
* ✅ **Ashby** (`jobs.ashbyhq.com/*`)
* ✅ **Lever** (`jobs.lever.co/*`)
* ✅ **Greenhouse** (`boards.greenhouse.io/*`, `job-boards.greenhouse.io/*`)
* ✅ **Recrew** (`*.recrew.ai/*`, `talent.recrew.ai/*`)
* ✅ **Work at a Startup / YC** (`workatastartup.com/*`)
* ✅ **Wellfound / AngelList** (`wellfound.com/*`)
* ✅ **BambooHR** (`*.bamboohr.com/*`)
* ✅ **SmartRecruiters** (`jobs.smartrecruiters.com/*`)
* ✅ **Pinpoint / Breezy / Personio / Freehire**

---

## 3. Features & Keyboard Shortcuts

* **`⚡ Auto-Fill Form` Floating Widget:** A sleek floating widget appears automatically on every supported application page.
* **Keyboard Shortcut (`Alt+A` or `Option+A`):** Hit `Alt+A` on your keyboard to instantly trigger autofill without touching your mouse.
* **React 16+ & Vue 3 Fiber Event Dispatcher:** Bypasses React's internal value tracking setter to ensure controlled form state, validation listeners, and dirty checks update immediately.
* **📄 Resume Dropzone Highlighter:** Highlights the file upload dropzone in a bright dashed border with a clear badge so you can drag-and-drop your tailored PDF in one second.
* **📋 1-Click Copy Cover Note:** Automatically copies your tailored pitch / cover note to your clipboard whenever you auto-fill.
* **Comprehensive Screening Logic:**
  * **Notice Period:** 45 days (45)
  * **Expected CTC:** ₹28 LPA (`28` / `2800000` / `$110,000`)
  * **Current CTC:** 8.4 LPA (`8.4` / `840000`)
  * **Experience:** Total 6.8 YOE (React: 6, Next.js: 4, TS: 6, Testing: 5, Node: 4, Python: 3)
  * **Work Authorization & Relocation:** Pre-sets standard yes/no answers for India/Remote.
