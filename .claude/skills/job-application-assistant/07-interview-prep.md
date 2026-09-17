---
framework_version: 1.0.0
---

# Interview Preparation Guide

<!-- SETUP: STAR examples are personalized by running /setup based on your actual experience -->

## STAR Format

Structure answers as: **Situation** (context), **Task** (your responsibility), **Action** (what you did), **Result** (outcome).

Keep answers to 1-2 minutes. Be specific. End with what you learned or would do differently.

## Ready-Made STAR Examples

### 1. Multi-Country Payroll & Statutory Balancing (Complex Domain Engineering)
**S:** Acme needed to calculate multi-country payroll across India, UAE, and Malaysia with strict statutory compliance (ESI, TDS, PF, PT, LWF, Bonus, Gratuity). In India, ESI calculations and gross salary balancing presented non-linear rounding dependencies.
**T:** Own the frontend engineering and computation logic for payroll setup, salary registers, and statutory dependency workflows.
**A:** Engineered a closed-form ESI balancing calculation and structured payroll computation logic handling complex CTC breakups, tax deductions, and multi-region reporting with robust data validation.
**R:** Delivered reliable, error-free payroll calculations used by enterprise clients across India, UAE, and Malaysia; simplified statutory compliance and Form 16 reporting.
**Use for:** "Tell me about a time you solved a complex technical or business problem", "How do you handle mission-critical financial / business logic?"

### 2. Modernizing Legacy AngularJS to React (Architecture & Migration)
**S:** Core admin workflows were built on legacy AngularJS, creating maintainability friction and slowing down feature delivery across Setup, L&D, Attendance, and Skill Matrix surfaces.
**T:** Incrementally migrate and modernize employee and setup interfaces to React without causing regressions in active production operations.
**A:** Built a coexistence strategy using Redux Toolkit, reusable shared UI components, and modular React surfaces that interfaced seamlessly alongside the legacy AngularJS shell.
**R:** Improved developer velocity, maintainability, and user experience across major modules, enabling smooth ongoing transitions without downtime or platform rewrites.
**Use for:** "Describe your experience with legacy migrations", "How do you modernize legacy code while keeping production stable?"

### 3. AI-Assisted Recruitment & L&D Lifecycle (AI Integration)
**S:** Recruitment and L&D teams spent significant manual effort parsing candidate resumes, screening candidates against job requirements, and creating job descriptions.
**T:** Streamline candidate matching and job description generation within the HRMS application.
**A:** Integrated Gemini AI into the recruitment and L&D workflows, building automated resume parsing, candidate-job matching algorithms, and automated JD generation tools directly into the frontend interface.
**R:** Drastically accelerated recruiter screening workflows and enhanced employee skills matching within the platform.
**Use for:** "How have you integrated AI into production web applications?", "Tell me about a feature you built that drove business productivity."

### 4. Project Nexus Multi-Tenant Booking SaaS (System Design & Rigor)
**S:** Service businesses required a reliable, mobile-first appointment booking platform that managed both advance reservations and walk-in queues under multi-tenant isolation.
**T:** Architect an independent, production-grade SaaS platform from scratch with high architectural discipline.
**A:** Built Project Nexus with Next.js 16, React 19, TypeScript, Tailwind v4, Supabase (RLS), and Drizzle ORM. Designed an explicit booking state machine (`confirmed` $\to$ `checked-in` $\to$ `completed`), 15 modular feature directories, 30 Architecture Decision Records (ADRs), dual-language i18n, and 14 Playwright test suites.
**R:** Delivered an end-to-end multi-tenant platform with automated testing, observability (Sentry), and comprehensive architectural documentation.
**Use for:** "Walk me through a project you architected from scratch", "How do you ensure code quality and maintainability in large frontends?"

## Common Tough Questions

### "Why are you looking for a new opportunity?"
> "I've spent over 6 years at Acme building deep domain expertise in multi-country HRMS, payroll, and complex frontend architectures. Having led major React modernizations, statutory engines, and AI integrations, I am looking to take on my next challenge—either as a Senior Frontend / Lead Product Engineer in a high-growth product SaaS or AI-driven company where I can drive large-scale web architecture."

### "How do you stay up-to-date with frontend and AI developments?"
> "I actively build and ship independent open-source and SaaS projects. For example, I built Project Nexus on Next.js 16/React 19 with Tailwind v4, engineered `agy-orchestrator` (a multi-model coding CLI with review gates), and created Universal AI Brain using the Model Context Protocol (MCP) and telemetry."

### "Where do you see yourself in 5 years?"
> "As a Staff Frontend Engineer or Engineering Lead driving frontend technical vision, design systems, and AI-native user interfaces for enterprise-grade SaaS products."

## Questions You Should Ask Interviewers

### About the Role
- "What does a typical week look like in this role?"
- "What would success look like in the first 6 months?"
- "What's the biggest challenge the team is facing right now?"

### About the Team
- "How big is the team, and how do you divide work?"
- "What does the development/project lifecycle look like, from idea to production?"
- "How do you onboard new team members?"

### About Tech & Growth
- "What's your current tech stack for [relevant area]?"
- "Is there room to grow into more architectural or strategic decisions?"
- "How does the team stay current with new tools and methods?"

### About Culture (use these to prevent disappointment)
- "How would you describe the team culture?"
- "What does professional development look like here?"
- "Is there flexibility for remote/hybrid work?"
- "What's the balance between development/new projects and maintenance work?"
- "How would you describe the leadership style in this team?"
- "What do people who thrive here have in common?"

## Phone/Video Interview Tips
- Have STAR examples written out (use this file)
- Keep a glass of water nearby
- Smile when speaking (it changes your tone)
- Ask for clarification if a question is vague
- It's OK to take 5 seconds to think before answering
- End with: "Is there anything else you'd like to know about my background?"

## After the Application (Best Practice)

### Follow-Up Etiquette
- **Don't call to "stand out"** or to learn more about the role post-submission - this risks a negative impression
- If the employer specified a timeline, respect it and wait
- If no timeline was given and significant time has passed (2+ weeks), a brief call to ask about status is acceptable
- If you have genuinely new, relevant information to share, a short follow-up is fine

### Thank-You Notes
- When you receive any update (interview invitation, rejection, or status update), send a brief thank-you message
- Express appreciation for their time and the process
- Keep it short (2-3 sentences)

## Roleplay Guidelines
When the user asks for interview practice:
1. Ask which role/company to simulate
2. Start with easy warm-up questions ("Tell me about yourself")
3. Progress to role-specific technical questions
4. Include 1-2 behavioral questions using the competencies from the job posting
5. End with a tough question or curveball
6. After each answer, give brief feedback: what worked, what to sharpen
7. Suggest which STAR example would work best for each question
