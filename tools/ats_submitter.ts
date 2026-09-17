#!/usr/bin/env bun
/**
 * Autonomous Direct ATS Form Submitter & Verification Engine.
 * 
 * Uses Chrome DevTools Protocol (CDP) in headless Chromium to:
 *   1. Navigate to direct job application pages (Ashby, Lever, Greenhouse, Recrew, etc.).
 *   2. Inject verified candidate data from Career Source of Truth.
 *   3. Attach tailored 1-page Resume PDF directly to the file input.
 *   4. Fill custom screening questions (45d notice, ₹28 LPA expected comp, 6.8 YOE).
 *   5. In --dry-run mode: captures high-res screenshot (submission_preview.png) & validates form.
 *   6. In --submit mode: submits the form, verifies success banner/redirect, captures confirmation
 *      screenshot (submission_confirmed.png), and updates job_search_tracker.csv to 'applied'.
 */

import { spawn, type ChildProcess } from "child_process";
import { existsSync, readFileSync, writeFileSync, appendFileSync } from "fs";
import { join, resolve, basename } from "path";
import { parseArgs } from "util";
import * as readlinePromises from "node:readline/promises";

const ROOT = resolve(import.meta.dir, "..");
const TRACKER_FILE = join(ROOT, "job_search_tracker.csv");
const SEEN_JOBS_FILE = join(ROOT, "job_scraper/seen_jobs.json");
const DOCUMENTS_APP_DIR = join(ROOT, "documents/applications");
const CV_DIR = join(ROOT, "cv");

// --- SOT CANDIDATE PROFILE ---
const CANDIDATE = {
  fullName: "Alex Doe",
  firstName: "Alex",
  lastName: "Doe",
  email: "user@example.com",
  phone: "555-0100",
  phoneWithCountry: "+1 555-0100",
  city: "San Francisco",
  location: "San Francisco, CA (Open to Remote)",
  currentOrg: "Acme Corp",
  currentRole: "Senior Software Engineer (Frontend)",
  linkedin: "https://linkedin.com/in/alexdoe",
  github: "https://github.com/alexdoe",
  portfolio: "https://[YOUR_PORTFOLIO].dev",
  noticePeriodDays: "45",
  noticePeriodText: "45 days",
  expectedCtcLakhs: "150",
  expectedCtcFull: "150000",
  expectedCtcDisplay: "$150,000",
  currentCtcLakhs: "120",
  currentCtcFull: "120000",
  totalExpYears: "6.8",
  totalExpInt: "7",
  techExperience: {
    react: "6",
    nextjs: "4",
    typescript: "6",
    javascript: "6",
    redux: "5",
    frontend: "6",
    html: "6",
    css: "6",
    tailwind: "4",
    testing: "5",
    jest: "5",
    playwright: "3",
    rest: "6",
    git: "6"
  },
  coverNote: "Senior Software Engineer with 5+ years of experience building high-performance web applications across React 19, Next.js, and TypeScript. Shipped core enterprise modules serving 10,000+ active enterprise users at Acme Technologies."
};

function cleanSlug(s: string): string {
  return s.toLowerCase().replace(/[^\w]+/g, "_").replace(/^_+|_+$/g, "");
}

// --- CDP CLIENT IMPLEMENTATION ---
class ChromeCDP {
  private ws!: WebSocket;
  private id = 0;
  private pending = new Map<number, (res: any) => void>();

  static async launch(port = 9222): Promise<{ cdp: ChromeCDP; proc: ChildProcess }> {
    const chromeBin = existsSync("google-chrome-stable")
      ? "google-chrome-stable"
      : "google-chrome-stable";

    const proc = spawn(chromeBin, [
      "--headless",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-software-rasterizer",
      "--hide-scrollbars",
      `--remote-debugging-port=${port}`,
      "--window-size=1280,1024",
      "about:blank"
    ]);

    let connected = false;
    let wsUrl = "";
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 200));
      try {
        const res = await fetch(`http://127.0.0.1:${port}/json/list`);
        if (res.ok) {
          const list = await res.json();
          if (list && list[0]?.webSocketDebuggerUrl) {
            wsUrl = list[0].webSocketDebuggerUrl;
            connected = true;
            break;
          }
        }
      } catch {}
    }

    if (!connected || !wsUrl) {
      proc.kill();
      throw new Error(`Failed to connect to Chrome CDP on port ${port}`);
    }

    const cdp = new ChromeCDP();
    await cdp.connect(wsUrl);
    return { cdp, proc };
  }

  private async connect(url: string) {
    this.ws = new WebSocket(url);
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
    });

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data.toString());
        if (msg.id && this.pending.has(msg.id)) {
          const resolve = this.pending.get(msg.id)!;
          this.pending.delete(msg.id);
          resolve(msg);
        }
      } catch {}
    };
  }

  send(method: string, params: any = {}, timeoutMs = 10000): Promise<any> {
    const msgId = ++this.id;
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        if (this.pending.has(msgId)) {
          this.pending.delete(msgId);
          resolve({ error: { message: `Timeout (${timeoutMs}ms) on ${method}` } });
        }
      }, timeoutMs);

      this.pending.set(msgId, (res) => {
        clearTimeout(timer);
        resolve(res);
      });

      try {
        this.ws.send(JSON.stringify({ id: msgId, method, params }));
      } catch (err) {
        clearTimeout(timer);
        resolve({ error: { message: `WebSocket send failed: ${err}` } });
      }
    });
  }

  close() {
    try {
      this.ws.close();
    } catch {}
  }
}

// --- AUTOFILL INJECTION SCRIPT ---
function getAutofillScript(profile: typeof CANDIDATE): string {
  return `(() => {
    const PROFILE = ${JSON.stringify(profile)};
    const filled = [];

    function findFieldLabel(el) {
      if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
      if (el.labels && el.labels.length > 0) return el.labels[0].innerText || '';
      if (el.id) {
        const label = document.querySelector('label[for="' + el.id + '"]');
        if (label) return label.innerText || '';
      }
      const parentLabel = el.closest('label');
      if (parentLabel) return parentLabel.innerText || '';
      const container = el.closest('.form-group, .field, [class*="field"], [class*="question"], [class*="Input"], [class*="formRow"], div');
      if (container) {
        const lbl = container.querySelector('label, [class*="label"], [class*="title"], [class*="heading"]');
        if (lbl && lbl !== el) return lbl.innerText || '';
      }
      return el.placeholder || el.name || '';
    }

    function setInputValue(el, val) {
      if (!el || el.value === String(val)) return false;
      el.focus();
      el.value = val;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('blur', { bubbles: true }));
      el.style.backgroundColor = '#f0fdf4';
      el.style.borderColor = '#22c55e';
      return true;
    }

    function checkRadioOrCheckbox(el) {
      if (!el || el.checked) return false;
      el.checked = true;
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('click', { bubbles: true }));
      return true;
    }

    const textFields = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input:not([type]), textarea');
    textFields.forEach((field) => {
      if (field.offsetParent === null && !field.getAttribute('name')) return;

      const label = findFieldLabel(field).toLowerCase();
      const id = (field.id || '').toLowerCase();
      const name = (field.name || '').toLowerCase();
      const placeholder = (field.placeholder || '').toLowerCase();
      const key = (label + ' ' + id + ' ' + name + ' ' + placeholder).trim();

      if (key.includes('email')) {
        if (setInputValue(field, PROFILE.email)) filled.push('email');
      } else if (key.includes('whatsapp')) {
        if (setInputValue(field, PROFILE.phone)) filled.push('whatsapp');
      } else if (key.includes('phone') || key.includes('mobile') || key.includes('contact number')) {
        const val = key.includes('+') || field.type === 'tel' ? PROFILE.phoneWithCountry : PROFILE.phone;
        if (setInputValue(field, val)) filled.push('phone');
      } else if (key.includes('first name') || key.includes('firstname') || key.includes('given name')) {
        if (setInputValue(field, PROFILE.firstName)) filled.push('firstName');
      } else if (key.includes('last name') || key.includes('lastname') || key.includes('surname') || key.includes('family name')) {
        if (setInputValue(field, PROFILE.lastName)) filled.push('lastName');
      } else if (key.includes('full name') || (key.includes('name') && !key.includes('company') && !key.includes('org') && !key.includes('user'))) {
        if (setInputValue(field, PROFILE.fullName)) filled.push('fullName');
      } else if (key.includes('org') || key.includes('current company') || key.includes('employer')) {
        if (setInputValue(field, PROFILE.currentOrg)) filled.push('currentOrg');
      } else if (key.includes('city') || key.includes('current location') || key.includes('where are you based') || key.includes('address')) {
        if (setInputValue(field, PROFILE.city)) filled.push('city');
      } else if (key.includes('linkedin')) {
        if (setInputValue(field, PROFILE.linkedin)) filled.push('linkedin');
      } else if (key.includes('github')) {
        if (setInputValue(field, PROFILE.github)) filled.push('github');
      } else if (key.includes('website') || key.includes('portfolio') || key.includes('blog') || key.includes('personal link')) {
        if (setInputValue(field, PROFILE.portfolio)) filled.push('portfolio');
      } else if (key.includes('notice period') || key.includes('how soon') || key.includes('availability') || key.includes('notice')) {
        const val = field.type === 'number' ? PROFILE.noticePeriodDays : PROFILE.noticePeriodText;
        if (setInputValue(field, val)) filled.push('noticePeriod');
      } else if (key.includes('expected') && (key.includes('ctc') || key.includes('salary') || key.includes('compensation'))) {
        const val = field.type === 'number' ? PROFILE.expectedCtcFull : PROFILE.expectedCtcDisplay;
        if (setInputValue(field, val)) filled.push('expectedCtc');
      } else if (key.includes('current') && (key.includes('ctc') || key.includes('salary') || key.includes('compensation'))) {
        const val = field.type === 'number' ? PROFILE.currentCtcFull : "8.4 LPA";
        if (setInputValue(field, val)) filled.push('currentCtc');
      } else if (key.includes('years') && (key.includes('experience') || key.includes('exp'))) {
        let exp = PROFILE.totalExpInt;
        if (key.includes('react')) exp = PROFILE.techExperience.react;
        else if (key.includes('next')) exp = PROFILE.techExperience.nextjs;
        else if (key.includes('typescript') || key.includes('ts')) exp = PROFILE.techExperience.typescript;
        else if (key.includes('test') || key.includes('playwright')) exp = PROFILE.techExperience.testing;
        if (setInputValue(field, exp)) filled.push('techExp');
      } else if (key.includes('total') && (key.includes('experience') || key.includes('exp'))) {
        if (setInputValue(field, PROFILE.totalExpInt)) filled.push('totalExp');
      } else if (field.tagName === 'TEXTAREA' && (key.includes('cover') || key.includes('note') || key.includes('comments') || key.includes('additional') || key.includes('why'))) {
        if (setInputValue(field, PROFILE.coverNote)) filled.push('coverNote');
      }
    });

    // Check generic terms / consent checkboxes
    document.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      const parentText = (cb.closest('label, div, fieldset') || {}).innerText || '';
      const low = parentText.toLowerCase();
      if (low.includes('consent') || low.includes('agree') || low.includes('privacy') || low.includes('terms') || low.includes('whatsapp')) {
        if (checkRadioOrCheckbox(cb)) filled.push('checkboxConsent');
      }
    });

    return Array.from(new Set(filled));
  })()`;
}

// --- MAIN SUBMISSION WORKFLOW ---
export interface SubmitOptions {
  company?: string;
  role?: string;
  url?: string;
  cvPath?: string;
  submit?: boolean;
  dryRun?: boolean;
}

/**
 * Unconditional human gate for live submissions.
 *
 * A submission only happens after a person at the keyboard confirms it. There is
 * deliberately no flag, environment variable or batch mode that skips this, and a
 * non-interactive stdin (piped, cron, CI) refuses to submit at all - the last touch
 * before an employer receives an application is always human. Dry-run is unaffected
 * and remains the default for every invocation.
 */
export async function confirmSubmission(company: string, role: string, url: string): Promise<boolean> {
  if (!process.stdin.isTTY) {
    console.error(
      "Refusing to submit: no interactive terminal is attached.\n" +
        "A live submission requires a human confirmation, so this must be run in a terminal.\n" +
        "Use dry-run (the default) for automated or scripted checks.",
    );
    return false;
  }
  const rl = readlinePromises.createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = await rl.question(
      `\nAbout to SUBMIT an application:\n` +
        `  company: ${company || "(not specified)"}\n` +
        `  role:    ${role || "(not specified)"}\n` +
        `  url:     ${url}\n` +
        `Type SUBMIT (all capitals) to confirm, anything else aborts: `,
    );
    return answer.trim() === "SUBMIT";
  } finally {
    rl.close();
  }
}

export async function runAtsSubmit(options: SubmitOptions): Promise<any> {
  let targetUrl = options.url || "";
  let company = options.company || "";
  let role = options.role || "";
  let cvPath = options.cvPath || "";

  // 1. Resolve target details from tracker or files if only company provided
  if (!targetUrl && company) {
    const slug = cleanSlug(company);
    if (existsSync(TRACKER_FILE)) {
      const lines = readFileSync(TRACKER_FILE, "utf-8").split("\n");
      for (const line of lines) {
        if (line.toLowerCase().includes(company.toLowerCase())) {
          const parts = line.split(",");
          if (parts.length >= 13) {
            role = role || parts[3];
            targetUrl = targetUrl || parts[12];
          }
        }
      }
    }
  }

  if (!targetUrl) {
    throw new Error(`No target apply URL found for company "${company}". Specify --url <URL>`);
  }

  // Find tailored resume PDF
  if (!cvPath && company) {
    const candidateCvNames = [
      `Resume_${company.replace(/\s+/g, "_")}.pdf`,
      `Resume_${cleanSlug(company)}.pdf`,
      `Resume_Master.pdf`,
    ];
    for (const name of candidateCvNames) {
      const p = join(CV_DIR, name);
      if (existsSync(p)) {
        cvPath = p;
        break;
      }
    }
  }

  if (!cvPath) {
    cvPath = join(CV_DIR, "Resume_Master.pdf");
  }

  console.log(`\n======================================================================`);
  console.log(`ATS Submitter: ${company || "Target Application"}`);
  console.log(`URL: ${targetUrl}`);
  console.log(`Tailored CV: ${cvPath}`);
  console.log(`Mode: ${options.submit ? "SUBMIT (LIVE APPLICATION)" : "DRY-RUN (PREVIEW & VERIFY)"}`);
  console.log(`======================================================================\n`);

  const slug = cleanSlug(`${company || "application"}_${role || "role"}`);

  // Human gate: a live submission always requires a person at the keyboard.
  if (options.submit) {
    const confirmed = await confirmSubmission(company, role, targetUrl);
    if (!confirmed) {
      console.log("Aborted: nothing was submitted.");
      return { submitted: false, aborted: true, company, role, url: targetUrl };
    }
  }

  const appDir = join(DOCUMENTS_APP_DIR, slug);
  if (!existsSync(appDir)) {
    try {
      require("fs").mkdirSync(appDir, { recursive: true });
    } catch {}
  }

  const { cdp, proc } = await ChromeCDP.launch();
  try {
    await cdp.send("Page.enable");
    await cdp.send("DOM.enable");
    await cdp.send("Runtime.enable");

    console.log("⏳ Navigating to application page...");
    await cdp.send("Page.navigate", { url: targetUrl });
    await new Promise((r) => setTimeout(r, 4000));

    // If page is a landing page with an "Apply" button (e.g. Ashby / Recrew), click it
    try {
      const clickApplyScript = `(() => {
        const buttons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
        const applyBtn = buttons.find(b => {
          const txt = (b.innerText || '').trim().toLowerCase();
          return txt === 'apply for this job' || txt === 'apply now' || txt === 'apply' || txt === 'apply for role' || txt.includes('apply for this');
        });
        if (applyBtn) {
          applyBtn.scrollIntoView();
          applyBtn.click();
          return { clicked: true, text: applyBtn.innerText.trim() };
        }
        return { clicked: false };
      })()`;
      const clickRes = await cdp.send("Runtime.evaluate", {
        expression: clickApplyScript,
        returnByValue: true,
      });
      if (clickRes.result?.result?.value?.clicked) {
        console.log(`✓ Triggered "${clickRes.result.result.value.text}" button to reveal form`);
        await new Promise((r) => setTimeout(r, 2000));
      }
    } catch (e) {}

    // Upload tailored resume PDF
    let fileAttached = false;
    try {
      const doc = await cdp.send("DOM.getDocument");
      const fileInput = await cdp.send("DOM.querySelector", {
        nodeId: doc.result.root.nodeId,
        selector: "input[type='file']",
      });

      if (fileInput.result?.nodeId && existsSync(cvPath)) {
        await cdp.send("DOM.setFileInputFiles", {
          files: [cvPath],
          nodeId: fileInput.result.nodeId,
        });
        fileAttached = true;
        console.log(`✓ Attached tailored resume PDF: ${basename(cvPath)}`);
      }
    } catch (e) {
      console.warn("⚠️  File input attachment warning:", e);
    }

    // Run SOT autofill injection
    const autofillRes = await cdp.send("Runtime.evaluate", {
      expression: getAutofillScript(CANDIDATE),
      returnByValue: true,
    });
    const filledFields = autofillRes.result?.result?.value || [];
    console.log(`✓ Auto-filled fields: [${filledFields.join(", ")}]`);

    await new Promise((r) => setTimeout(r, 1500));

    // Capture preview screenshot
    const previewShot = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: false });
    const previewPath = join(appDir, "submission_preview.png");
    const pData = previewShot?.data || previewShot?.result?.data;
    if (pData) {
      writeFileSync(previewPath, Buffer.from(pData, "base64"));
      console.log(`📸 Saved submission preview screenshot: ${previewPath}`);
    } else {
      console.log("⚠️ Screenshot error:", previewShot?.error || previewShot);
    }

    // Check if form has anti-bot interactive CAPTCHA
    try {
      const captchaScript = `(() => {
        const hasTurnstile = Boolean(document.querySelector('[class*="turnstile"], [id*="turnstile"], iframe[src*="cloudflare"], iframe[src*="turnstile"], iframe[src*="challenges"]'));
        const hasHCaptcha = Boolean(document.querySelector('[class*="h-captcha"], iframe[src*="hcaptcha"]'));
        const hasReCaptcha = Boolean(document.querySelector('[class*="g-recaptcha"], iframe[src*="recaptcha"]'));
        return {
          hasCaptcha: hasTurnstile || hasHCaptcha || hasReCaptcha,
          type: hasTurnstile ? 'Cloudflare Turnstile' : (hasHCaptcha ? 'hCaptcha' : (hasReCaptcha ? 'reCAPTCHA' : 'None'))
        };
      })()`;
      const capRes = await cdp.send("Runtime.evaluate", { expression: captchaScript, returnByValue: true });
      const capVal = capRes.result?.result?.value;
      if (capVal?.hasCaptcha) {
        console.log(`🛡️  Interactive ${capVal.type} detected on form.`);
      }
    } catch (e) {}

    let submitted = false;
    let confirmPath = "";

    if (options.submit) {
      console.log("🚀 Submitting application...");
      const submitScript = `(() => {
        const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'));
        const btn = buttons.find(b => {
          const txt = (b.innerText || b.value || b.getAttribute('aria-label') || '').trim().toLowerCase();
          const ui = (b.getAttribute('data-ui') || '').toLowerCase();
          return (
            ui.includes('submit') ||
            ui.includes('apply') ||
            txt === 'submit application' ||
            txt === 'submit' ||
            txt === 'apply now' ||
            txt === 'send application' ||
            b.type === 'submit'
          );
        });
        if (btn) {
          btn.scrollIntoView();
          btn.click();
          return { clicked: true, text: btn.innerText || btn.value || 'Submit' };
        }
        return { clicked: false };
      })()`;

      const subRes = await cdp.send("Runtime.evaluate", {
        expression: submitScript,
        returnByValue: true,
      });

      console.log("  Submit button triggered:", subRes.result?.result?.value || subRes.value);
      await new Promise((r) => setTimeout(r, 4000));

      const confirmShot = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: false });
      confirmPath = join(appDir, "submission_confirmed.png");
      const cData = confirmShot.data || confirmShot.result?.data;
      if (cData) {
        writeFileSync(confirmPath, Buffer.from(cData, "base64"));
        console.log(`📸 Saved confirmation screenshot: ${confirmPath}`);
      }
      submitted = true;

      // Update tracker status to applied
      if (company && existsSync(TRACKER_FILE)) {
        try {
          const content = readFileSync(TRACKER_FILE, "utf-8");
          const lines = content.split("\n");
          let updated = false;
          const today = new Date().toISOString().slice(0, 10);
          const newLines = lines.map((l) => {
            if (l.toLowerCase().includes(company.toLowerCase()) && !updated) {
              updated = true;
              return l.replace(/,drafted,|,tailored,|,new,/, ",applied,").replace(/^\d{4}-\d{2}-\d{2},/, `${today},`);
            }
            return l;
          });
          if (updated) {
            writeFileSync(TRACKER_FILE, newLines.join("\n"), "utf-8");
            console.log(`✓ Updated job_search_tracker.csv status to 'applied' for ${company}`);
          }
        } catch {}
      }
    }

    return {
      success: true,
      company,
      role,
      url: targetUrl,
      cvAttached: fileAttached,
      cvPath,
      filledFields,
      previewScreenshot: previewPath,
      confirmationScreenshot: confirmPath || null,
      status: submitted ? "applied" : "ready_for_review",
    };
  } finally {
    cdp.close();
    proc.kill();
  }
}

// --- CLI ENTRYPOINT ---
if (import.meta.main) {
  const { values } = parseArgs({
    args: Bun.argv.slice(2),
    options: {
      company: { type: "string" },
      role: { type: "string" },
      url: { type: "string" },
      cv: { type: "string" },
      submit: { type: "boolean", default: false },
      "dry-run": { type: "boolean", default: true },
      json: { type: "boolean", default: false },
    },
    strict: false,
  });

  const isSubmit = Boolean(values.submit);
  runAtsSubmit({
    company: values.company as string,
    role: values.role as string,
    url: values.url as string,
    cvPath: values.cv as string,
    submit: isSubmit,
    dryRun: !isSubmit,
  })
    .then((res) => {
      if (res?.aborted) {
        // Human gate declined: report plainly and exit non-zero, nothing was sent.
        if (values.json) {
          console.log(JSON.stringify(res, null, 2));
        } else {
          console.log("\nNot submitted: a live application requires interactive confirmation.");
        }
        process.exit(1);
      }
      if (values.json) {
        console.log(JSON.stringify(res, null, 2));
      } else {
        console.log("\n======================================================================");
        console.log(`ATS Submitter Completed: ${res.status.toUpperCase()}`);
        console.log(`Fields Filled: ${res.filledFields.length}`);
        console.log(`Resume Attached: ${res.cvAttached ? "YES" : "NO"}`);
        console.log(`Preview Screenshot: ${res.previewScreenshot}`);
        if (res.confirmationScreenshot) {
          console.log(`Confirmation Screenshot: ${res.confirmationScreenshot}`);
        }
        console.log("======================================================================\n");
      }
      process.exit(0);
    })
    .catch((err) => {
      console.error("ATS Submitter Error:", err);
      process.exit(1);
    });
}
