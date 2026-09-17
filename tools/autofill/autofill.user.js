// ==UserScript==
// @name         AI Job Application Super Auto-Filler (SOT Grounded)
// @namespace    https://[YOUR_PORTFOLIO].dev
// @version      2.0.0
// @description  Instantly auto-fills job application forms across LinkedIn, Workable, Ashby, Lever, Greenhouse, Recrew, Wellfound, BambooHR, SmartRecruiters, and YC with verified candidate data from Career Source of Truth.
// @author       Alex Doe
// @match        https://*.linkedin.com/*
// @match        https://*.workable.com/*
// @match        https://apply.workable.com/*
// @match        https://jobs.ashbyhq.com/*
// @match        https://jobs.lever.co/*
// @match        https://boards.greenhouse.io/*
// @match        https://job-boards.greenhouse.io/*
// @match        https://*.recrew.ai/*
// @match        https://talent.recrew.ai/*
// @match        https://wellfound.com/*
// @match        https://*.workatastartup.com/*
// @match        https://*.bamboohr.com/*
// @match        https://jobs.smartrecruiters.com/*
// @match        https://*.pinpointhq.com/*
// @match        https://*.breezy.hr/*
// @match        https://*.personio.com/*
// @match        https://*.rippling-ats.com/*
// @match        https://*.djinni.co/*
// @match        https://*.hirist.tech/*
// @match        https://*.hirist.com/*
// @match        https://*.naukri.com/*
// @match        https://*.whatjobs.com/*
// @match        https://*.freehire.me/*
// @grant        GM_setClipboard
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // ==========================================================================
  // 1. CANDIDATE SOURCE OF TRUTH (CAREER_SOURCE_OF_TRUTH.md STRICT ALIGNMENT)
  // ==========================================================================
  const PROFILE = {
    fullName: "Alex Doe",
    firstName: "Alex",
    lastName: "Doe",
    email: "user@example.com",
    phone: "555-0100",
    phoneWithCountry: "+1 555-0100",
    phoneCountryCode: "United States (+1)",
    phonePrefix: "+1",
    city: "San Francisco",
    state: "CA",
    country: "United States",
    location: "San Francisco, CA (Open to Remote)",
    currentOrg: "Acme Corp",
    currentTitle: "Senior Software Engineer (Frontend & Systems)",
    currentCompany: "Acme Corp",
    linkedin: "https://linkedin.com/in/alexdoe",
    github: "https://github.com/alexdoe",
    portfolio: "https://[YOUR_PORTFOLIO].dev",
    website: "https://[YOUR_PORTFOLIO].dev",
    
    // Compensation & Notice Period (Ground Truth)
    noticePeriodDays: "45",
    noticePeriodWeeks: "6",
    noticePeriodMonths: "1.5",
    noticePeriodText: "45 days",
    servingNotice: "No",
    expectedCtcLakhs: "150",
    expectedCtcFull: "150000",
    expectedCtcDisplay: "$150,000",
    expectedSalaryUsd: "110000",
    expectedSalaryUsdDisplay: "$110,000",
    currentCtcLakhs: "120",
    currentCtcFull: "120000",
    currentCtcDisplay: "$120,000",
    
    // Experience & Metrics
    totalExperienceYears: "6.8",
    totalExpInt: "7",
    techExperience: {
      react: "6",
      nextjs: "4",
      typescript: "6",
      javascript: "6",
      python: "3",
      nodejs: "4",
      redux: "5",
      frontend: "6",
      fullstack: "5",
      html: "6",
      css: "6",
      tailwind: "4",
      testing: "5",
      jest: "5",
      playwright: "3",
      vitest: "2",
      rest: "6",
      openapi: "4",
      webhooks: "5",
      git: "6",
      ai: "3",
      sql: "4"
    },
    
    // Core Tailored Pitch / Cover Note
    coverNote: "Senior Software Engineer with 5+ years of experience building high-performance web applications across React 19, Next.js, and TypeScript. Shipped core enterprise modules serving 10,000+ active enterprise users at Acme Technologies."
  };

  // ==========================================================================
  // 2. SYNTHETIC EVENT DISPATCHER (REACT 16+ & VUE 3 FIBER COMPATIBLE)
  // ==========================================================================
  function setNativeValue(el, val) {
    if (!el) return false;
    const strVal = String(val);
    if (el.value === strVal) return false;

    el.focus();

    // Bypass React / Angular input value setters
    const nativeInputSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value"
    )?.set;
    const nativeTextAreaSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      "value"
    )?.set;

    if (el.tagName === "TEXTAREA" && nativeTextAreaSetter) {
      nativeTextAreaSetter.call(el, strVal);
    } else if (el.tagName === "INPUT" && nativeInputSetter) {
      nativeInputSetter.call(el, strVal);
    } else {
      el.value = strVal;
    }

    // Trigger synthetic bubbling events
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));

    // Visual highlight feedback
    el.style.transition = "all 0.3s ease";
    el.style.backgroundColor = "#f0fdf4";
    el.style.borderColor = "#22c55e";
    el.style.boxShadow = "0 0 0 2px rgba(34, 197, 94, 0.2)";
    return true;
  }

  function setSelectValue(el, matchText) {
    if (!el) return false;
    const lower = String(matchText).toLowerCase();
    for (let i = 0; i < el.options.length; i++) {
      const opt = el.options[i];
      const optText = (opt.text || "").toLowerCase();
      const optVal = (opt.value || "").toLowerCase();
      if (optText.includes(lower) || optVal.includes(lower)) {
        el.selectedIndex = i;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.dispatchEvent(new Event("blur", { bubbles: true }));
        el.style.backgroundColor = "#f0fdf4";
        el.style.borderColor = "#22c55e";
        return true;
      }
    }
    return false;
  }

  function checkRadioOrCheckbox(el) {
    if (!el || el.checked) return false;
    el.checked = true;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("click", { bubbles: true }));
    return true;
  }

  // ==========================================================================
  // 3. FIELD IDENTIFIER & LABEL RESOLVER
  // ==========================================================================
  function findFieldLabel(el) {
    if (!el) return "";
    let labels = [];

    // 1. Direct label reference via ID
    if (el.id) {
      const directLbl = document.querySelector(`label[for="${el.id}"]`);
      if (directLbl) labels.push(directLbl.innerText);
    }

    // 2. Parent label element
    const parentLbl = el.closest("label");
    if (parentLbl) labels.push(parentLbl.innerText);

    // 3. Container-level headings and legends
    const container = el.closest(
      ".form-field, .form-group, .field, [class*='field'], [class*='question'], [class*='Input'], [class*='formRow'], .jobs-easy-apply-form-element, .fb-dash-form-element, fieldset, div"
    );
    if (container) {
      const heading = container.querySelector("label, legend, [class*='label'], [class*='title'], [class*='heading'], span");
      if (heading && heading !== el) labels.push(heading.innerText);
    }

    // 4. Attributes (aria-label, placeholder, name, id)
    if (el.getAttribute("aria-label")) labels.push(el.getAttribute("aria-label"));
    if (el.placeholder) labels.push(el.placeholder);
    if (el.name) labels.push(el.name);
    if (el.id) labels.push(el.id);

    return labels.join(" ").replace(/\s+/g, " ").trim();
  }

  // ==========================================================================
  // 4. MAIN AUTOFILL ENGINE
  // ==========================================================================
  function runAutoFill() {
    let filledCount = 0;
    const filledFields = [];

    // --- 4A. Text Inputs, Number, Tel, Email, Textareas ---
    const textFields = document.querySelectorAll(
      "input[type='text'], input[type='email'], input[type='tel'], input[type='number'], input:not([type]), textarea"
    );

    textFields.forEach((field) => {
      if (field.offsetParent === null && !field.getAttribute("name") && !field.id) return; // Ignore invisible

      const rawKey = findFieldLabel(field).toLowerCase();
      const key = rawKey.replace(/[_\-]/g, " ");

      // Email
      if (key.includes("email")) {
        if (setNativeValue(field, PROFILE.email)) {
          filledCount++;
          filledFields.push("Email");
        }
      }
      // WhatsApp
      else if (key.includes("whatsapp")) {
        if (setNativeValue(field, PROFILE.phone)) {
          filledCount++;
          filledFields.push("WhatsApp");
        }
      }
      // Phone / Mobile
      else if (key.includes("phone") || key.includes("mobile") || key.includes("contact number") || key.includes("telephone")) {
        const val = key.includes("country code") || key.includes("prefix")
          ? PROFILE.phonePrefix
          : (field.type === "tel" && key.includes("+") ? PROFILE.phoneWithCountry : PROFILE.phone);
        if (setNativeValue(field, val)) {
          filledCount++;
          filledFields.push("Phone");
        }
      }
      // First Name
      else if (key.includes("first name") || key.includes("firstname") || key.includes("given name") || key.includes("first_name")) {
        if (setNativeValue(field, PROFILE.firstName)) {
          filledCount++;
          filledFields.push("First Name");
        }
      }
      // Last Name
      else if (key.includes("last name") || key.includes("lastname") || key.includes("surname") || key.includes("family name") || key.includes("last_name")) {
        if (setNativeValue(field, PROFILE.lastName)) {
          filledCount++;
          filledFields.push("Last Name");
        }
      }
      // Full Name
      else if (key.includes("full name") || (key.includes("name") && !key.includes("company") && !key.includes("org") && !key.includes("user") && !key.includes("first") && !key.includes("last") && !key.includes("manager"))) {
        if (setNativeValue(field, PROFILE.fullName)) {
          filledCount++;
          filledFields.push("Full Name");
        }
      }
      // Current Company / Organization
      else if (key.includes("current company") || key.includes("current employer") || key.includes("current organization") || key.includes("org name") || key.includes("company name")) {
        if (setNativeValue(field, PROFILE.currentOrg)) {
          filledCount++;
          filledFields.push("Current Org");
        }
      }
      // Current Job Title
      else if (key.includes("current title") || key.includes("current role") || key.includes("job title") || key.includes("current designation")) {
        if (setNativeValue(field, PROFILE.currentTitle)) {
          filledCount++;
          filledFields.push("Current Title");
        }
      }
      // Location / City / Address
      else if (key.includes("city") || key.includes("current location") || key.includes("where are you based") || key.includes("address") || key.includes("location")) {
        const val = key.includes("country") ? PROFILE.country : (key.includes("state") ? PROFILE.state : PROFILE.city);
        if (setNativeValue(field, val)) {
          filledCount++;
          filledFields.push("Location");
        }
      }
      // LinkedIn URL
      else if (key.includes("linkedin")) {
        if (setNativeValue(field, PROFILE.linkedin)) {
          filledCount++;
          filledFields.push("LinkedIn");
        }
      }
      // GitHub URL
      else if (key.includes("github") || key.includes("git repository")) {
        if (setNativeValue(field, PROFILE.github)) {
          filledCount++;
          filledFields.push("GitHub");
        }
      }
      // Portfolio / Website / Personal URL
      else if (key.includes("website") || key.includes("portfolio") || key.includes("personal link") || key.includes("other url") || key.includes("blog")) {
        if (setNativeValue(field, PROFILE.portfolio)) {
          filledCount++;
          filledFields.push("Portfolio");
        }
      }
      // Notice Period / Availability
      else if (key.includes("notice period") || key.includes("how soon") || key.includes("availability") || key.includes("notice in days") || key.includes("joining time")) {
        const val = field.type === "number" ? PROFILE.noticePeriodDays : PROFILE.noticePeriodText;
        if (setNativeValue(field, val)) {
          filledCount++;
          filledFields.push("Notice Period (45d)");
        }
      }
      // Expected CTC / Salary / Compensation
      else if (key.includes("expected") && (key.includes("ctc") || key.includes("salary") || key.includes("compensation") || key.includes("remuneration") || key.includes("pay"))) {
        const isLpaOrSmallNumber = key.includes("lpa") || key.includes("lakh") || (field.max && Number(field.max) <= 1000);
        const isUsd = key.includes("usd") || key.includes("$");
        const val = isUsd
          ? (field.type === "number" ? PROFILE.expectedSalaryUsd : PROFILE.expectedSalaryUsdDisplay)
          : (isLpaOrSmallNumber ? PROFILE.expectedCtcLakhs : (field.type === "number" ? PROFILE.expectedCtcFull : PROFILE.expectedCtcDisplay));
        if (setNativeValue(field, val)) {
          filledCount++;
          filledFields.push("Expected CTC");
        }
      }
      // Current CTC / Salary
      else if (key.includes("current") && (key.includes("ctc") || key.includes("salary") || key.includes("compensation") || key.includes("remuneration") || key.includes("pay"))) {
        const isLpaOrSmallNumber = key.includes("lpa") || key.includes("lakh") || (field.max && Number(field.max) <= 1000);
        const val = isLpaOrSmallNumber ? PROFILE.currentCtcLakhs : (field.type === "number" ? PROFILE.currentCtcFull : PROFILE.currentCtcDisplay);
        if (setNativeValue(field, val)) {
          filledCount++;
          filledFields.push("Current CTC");
        }
      }
      // Specific Tech Experience
      else if (key.includes("years") && (key.includes("experience") || key.includes("exp"))) {
        let exp = PROFILE.totalExpInt;
        let label = "Total Exp";
        if (key.includes("react")) { exp = PROFILE.techExperience.react; label = "React Exp"; }
        else if (key.includes("next")) { exp = PROFILE.techExperience.nextjs; label = "Next.js Exp"; }
        else if (key.includes("typescript") || key.includes("ts")) { exp = PROFILE.techExperience.typescript; label = "TypeScript Exp"; }
        else if (key.includes("javascript") || key.includes("js")) { exp = PROFILE.techExperience.javascript; label = "JavaScript Exp"; }
        else if (key.includes("python")) { exp = PROFILE.techExperience.python; label = "Python Exp"; }
        else if (key.includes("node")) { exp = PROFILE.techExperience.nodejs; label = "Node Exp"; }
        else if (key.includes("test") || key.includes("playwright") || key.includes("jest")) { exp = PROFILE.techExperience.testing; label = "Testing Exp"; }
        
        if (setNativeValue(field, exp)) {
          filledCount++;
          filledFields.push(label);
        }
      }
      // Total Experience
      else if (key.includes("total") && (key.includes("experience") || key.includes("exp"))) {
        if (setNativeValue(field, PROFILE.totalExpInt)) {
          filledCount++;
          filledFields.push("Total Experience");
        }
      }
      // Summary / Cover Note / Why Apply / Tell us about yourself
      else if (field.tagName === "TEXTAREA" && (key.includes("cover") || key.includes("note") || key.includes("summary") || key.includes("why") || key.includes("additional") || key.includes("tell us") || key.includes("comments") || key.includes("message"))) {
        if (setNativeValue(field, PROFILE.coverNote)) {
          filledCount++;
          filledFields.push("Cover Note");
        }
      }
    });

    // --- 4B. Radio Buttons & Checkboxes ---
    const radios = document.querySelectorAll("input[type='radio']");
    radios.forEach((radio) => {
      const label = findFieldLabel(radio).toLowerCase();
      const parentContainer = radio.closest(".jobs-easy-apply-form-section, .fb-dash-form-element, fieldset, .form-group, .form-field, div") || {};
      const context = `${label} ${parentContainer.innerText || ""}`.toLowerCase();

      // Currently serving notice period? -> No
      if (context.includes("currently on notice") || context.includes("serving notice") || context.includes("is on notice")) {
        if (label === "no" || radio.value.toLowerCase() === "no") {
          if (checkRadioOrCheckbox(radio)) { filledCount++; filledFields.push("Serving Notice: No"); }
        }
      }
      // Legally authorized to work in India? -> Yes
      else if (context.includes("authorized to work") || context.includes("legally authorized") || context.includes("eligible to work") || context.includes("work authorization")) {
        if (label === "yes" || radio.value.toLowerCase() === "yes" || radio.value === "true") {
          if (checkRadioOrCheckbox(radio)) { filledCount++; filledFields.push("Work Authorization: Yes"); }
        }
      }
      // Require visa sponsorship for India? -> No
      else if (context.includes("sponsorship") || context.includes("visa")) {
        if (context.includes("india") || context.includes("future sponsorship") || context.includes("require sponsorship")) {
          if (label === "no" || radio.value.toLowerCase() === "no" || radio.value === "false") {
            if (checkRadioOrCheckbox(radio)) { filledCount++; filledFields.push("Visa Sponsorship: No"); }
          }
        }
      }
      // Willing to relocate / commute / hybrid / remote? -> Yes
      else if (context.includes("commute") || context.includes("relocate") || context.includes("hybrid") || context.includes("remote") || context.includes("san francisco") || context.includes("bay area") || context.includes("remote") || context.includes("est")) {
        if (label === "yes" || radio.value.toLowerCase() === "yes" || radio.value === "true") {
          if (checkRadioOrCheckbox(radio)) { filledCount++; filledFields.push("Location / Remote: Yes"); }
        }
      }
      // Agree to background check? -> Yes
      else if (context.includes("background check") || context.includes("reference check")) {
        if (label === "yes" || radio.value.toLowerCase() === "yes") {
          if (checkRadioOrCheckbox(radio)) { filledCount++; filledFields.push("Background Check: Yes"); }
        }
      }
    });

    // --- 4C. Dropdowns (<select>) ---
    const selects = document.querySelectorAll("select");
    selects.forEach((sel) => {
      const label = findFieldLabel(sel).toLowerCase();
      const key = `${label} ${(sel.id || "").toLowerCase()} ${(sel.name || "").toLowerCase()}`;

      if (key.includes("phone") || key.includes("code") || key.includes("country")) {
        if (setSelectValue(sel, "+91") || setSelectValue(sel, "India") || setSelectValue(sel, "91")) {
          filledCount++;
          filledFields.push("Phone Code (+91)");
        }
      } else if (key.includes("notice") || key.includes("availability") || key.includes("joining")) {
        if (setSelectValue(sel, "45") || setSelectValue(sel, "1 month") || setSelectValue(sel, "2 months") || setSelectValue(sel, "30-45")) {
          filledCount++;
          filledFields.push("Notice Dropdown");
        }
      } else if (key.includes("experience") || key.includes("years")) {
        if (setSelectValue(sel, "5-7") || setSelectValue(sel, "6") || setSelectValue(sel, "5+") || setSelectValue(sel, "6-8")) {
          filledCount++;
          filledFields.push("Experience Dropdown");
        }
      } else if (key.includes("authorized") || key.includes("eligibility") || key.includes("eligible")) {
        if (setSelectValue(sel, "yes") || setSelectValue(sel, "true")) {
          filledCount++;
          filledFields.push("Authorization: Yes");
        }
      } else if (key.includes("sponsorship")) {
        if (setSelectValue(sel, "no") || setSelectValue(sel, "false")) {
          filledCount++;
          filledFields.push("Sponsorship: No");
        }
      }
    });

    // --- 4D. Consent Checkboxes ---
    document.querySelectorAll("input[type='checkbox']").forEach((cb) => {
      const label = findFieldLabel(cb).toLowerCase();
      if (label.includes("consent") || label.includes("agree") || label.includes("privacy") || label.includes("terms") || label.includes("whatsapp")) {
        if (checkRadioOrCheckbox(cb)) {
          filledCount++;
          filledFields.push("Consent Checkbox");
        }
      }
    });

    // --- 4E. Highlight File Dropzone for PDF Resume Upload ---
    highlightResumeDropzone();

    // Show Toast Notification
    showToast(filledCount, filledFields);
  }

  // ==========================================================================
  // 5. RESUME DROPZONE HIGHLIGHTER
  // ==========================================================================
  function highlightResumeDropzone() {
    const fileInputs = document.querySelectorAll("input[type='file']");
    fileInputs.forEach((input) => {
      const container = input.closest(".dropzone, .file-upload, [class*='upload'], [class*='dropzone'], [class*='resume'], label, div") || input;
      container.style.border = "3px dashed #0284c7";
      container.style.backgroundColor = "#f0f9ff";
      container.style.borderRadius = "8px";
      container.style.padding = "14px";
      container.style.transition = "all 0.3s ease";
      
      let badge = container.querySelector("#sot-resume-badge");
      if (!badge) {
        badge = document.createElement("div");
        badge.id = "sot-resume-badge";
        badge.innerHTML = "📄 <strong>DROP TAILORED RESUME PDF HERE</strong>";
        badge.style.color = "#0369a1";
        badge.style.fontSize = "12px";
        badge.style.fontFamily = "sans-serif";
        badge.style.fontWeight = "700";
        badge.style.marginBottom = "6px";
        badge.style.textAlign = "center";
        container.prepend(badge);
      }
    });
  }

  // ==========================================================================
  // 6. TOAST NOTIFICATION
  // ==========================================================================
  function showToast(count, fields) {
    let toast = document.getElementById("sot-autofill-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "sot-autofill-toast";
      toast.style.position = "fixed";
      toast.style.bottom = "80px";
      toast.style.right = "20px";
      toast.style.zIndex = "9999999";
      toast.style.backgroundColor = "#0f172a";
      toast.style.color = "#ffffff";
      toast.style.border = "2px solid #22c55e";
      toast.style.borderRadius = "10px";
      toast.style.padding = "14px 18px";
      toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.3)";
      toast.style.fontFamily = "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif";
      toast.style.fontSize = "13px";
      toast.style.maxWidth = "320px";
      toast.style.transition = "all 0.3s ease";
      document.body.appendChild(toast);
    }

    toast.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-weight: 700; color: #4ade80; font-size: 14px;">⚡ Auto-Fill Complete</span>
        <span style="font-size: 11px; color: #94a3b8;">45d Notice | 6.8 YOE</span>
      </div>
      <div style="font-size: 12px; color: #e2e8f0; line-height: 1.4;">
        Populated <strong>${count} fields</strong> (${fields.slice(0, 4).join(", ")}${fields.length > 4 ? ` +${fields.length - 4} more` : ""}).
      </div>
      <div style="font-size: 11px; color: #38bdf8; margin-top: 6px; font-weight: 600;">
        ✓ Dropzone highlighted · Cover note copied to clipboard
      </div>
    `;

    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
    }, 4500);
  }

  // ==========================================================================
  // 7. FLOATING MINI-WIDGET
  // ==========================================================================
  function injectFloatingWidget() {
    if (document.getElementById("sot-autofill-hub")) return;

    const hub = document.createElement("div");
    hub.id = "sot-autofill-hub";
    hub.style.position = "fixed";
    hub.style.bottom = "20px";
    hub.style.right = "20px";
    hub.style.zIndex = "9999998";
    hub.style.display = "flex";
    hub.style.flexDirection = "column";
    hub.style.gap = "8px";
    hub.style.fontFamily = "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif";

    // Main Auto-Fill Button
    const mainBtn = document.createElement("button");
    mainBtn.innerHTML = "⚡ Auto-Fill Form <span style='font-size: 10px; opacity: 0.8; margin-left: 4px;'>(Alt+A)</span>";
    mainBtn.style.padding = "10px 16px";
    mainBtn.style.backgroundColor = "#0f172a";
    mainBtn.style.color = "#ffffff";
    mainBtn.style.border = "2px solid #38bdf8";
    mainBtn.style.borderRadius = "8px";
    mainBtn.style.fontSize = "13px";
    mainBtn.style.fontWeight = "700";
    mainBtn.style.cursor = "pointer";
    mainBtn.style.boxShadow = "0 4px 14px rgba(0,0,0,0.25)";
    mainBtn.style.transition = "all 0.2s ease";

    mainBtn.onmouseover = () => {
      mainBtn.style.backgroundColor = "#1e293b";
      mainBtn.style.transform = "translateY(-2px)";
    };
    mainBtn.onmouseout = () => {
      mainBtn.style.backgroundColor = "#0f172a";
      mainBtn.style.transform = "translateY(0)";
    };

    mainBtn.onclick = (e) => {
      e.preventDefault();
      runAutoFill();
      // Also copy cover note
      if (navigator.clipboard) {
        navigator.clipboard.writeText(PROFILE.coverNote).catch(() => {});
      }
    };

    // Quick Copy Cover Note Button
    const copyBtn = document.createElement("button");
    copyBtn.innerHTML = "📋 Copy Cover Note";
    copyBtn.style.padding = "7px 12px";
    copyBtn.style.backgroundColor = "#1e293b";
    copyBtn.style.color = "#94a3b8";
    copyBtn.style.border = "1px solid #475569";
    copyBtn.style.borderRadius = "6px";
    copyBtn.style.fontSize = "11px";
    copyBtn.style.fontWeight = "600";
    copyBtn.style.cursor = "pointer";
    copyBtn.style.transition = "all 0.2s ease";

    copyBtn.onclick = (e) => {
      e.preventDefault();
      if (navigator.clipboard) {
        navigator.clipboard.writeText(PROFILE.coverNote);
      }
      copyBtn.innerHTML = "✓ Copied Cover Note!";
      copyBtn.style.color = "#4ade80";
      setTimeout(() => {
        copyBtn.innerHTML = "📋 Copy Cover Note";
        copyBtn.style.color = "#94a3b8";
      }, 2500);
    };

    hub.appendChild(mainBtn);
    hub.appendChild(copyBtn);
    document.body.appendChild(hub);
  }

  // Keyboard shortcut Alt+A / Option+A
  window.addEventListener("keydown", (e) => {
    if (e.altKey && (e.key === "a" || e.key === "A")) {
      e.preventDefault();
      runAutoFill();
    }
  });

  // Watch DOM for single-page app transitions
  setInterval(injectFloatingWidget, 1500);
})();
