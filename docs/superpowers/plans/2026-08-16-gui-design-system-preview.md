# Sonus GUI Design System Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, browser-served design system preview for the future Sonus desktop GUI.

**Architecture:** `design-preview/index.html` owns semantic content, `styles.css` owns theme tokens and responsive component styling, and `app.js` owns testable theme persistence plus section navigation. Node's built-in test runner verifies theme behavior without frontend dependencies.

**Tech Stack:** HTML5, CSS custom properties, vanilla JavaScript, Pretendard webfont, Node.js built-in test runner, pytest

## Global Constraints

- Default to the light theme and use dark only after an explicit user toggle.
- Use `#2563EB` as the primary blue and cool neutral surfaces.
- Use Pretendard with system sans-serif fallbacks.
- Do not add a build step, JavaScript dependency, or Python runtime dependency.
- Keep the preview disconnected from the headset and Sonus device API.

---

### Task 1: Theme Behavior Contract

**Files:**
- Create: `design-preview/app.test.mjs`
- Create: `design-preview/app.js`

**Interfaces:**
- Produces: `resolveInitialTheme(storedTheme)`, `applyTheme(root, toggle, theme)`, and `toggleTheme(currentTheme, storage)`

- [ ] Write Node tests for the light default, explicit dark restoration, accessible DOM state, and `sonus-theme` persistence.
- [ ] Run `node --test design-preview/app.test.mjs` and confirm failure because `app.js` is missing.
- [ ] Implement the three exported functions and browser initialization with section observation.
- [ ] Run `node --test design-preview/app.test.mjs` and `node --check design-preview/app.js`; expect both to pass.

### Task 2: Restrained Panel Design System

**Files:**
- Create: `design-preview/index.html`
- Create: `design-preview/styles.css`

**Interfaces:**
- Consumes: theme behavior from `app.js`
- Produces: one responsive review page with Foundations, Typography, Colors, Spacing, and Components sections

- [ ] Create semantic navigation, theme toggle, principles, WH-1000XM6 status example, typography scale, color and spacing tokens, buttons, fields, switches, slider, and feedback examples.
- [ ] Define light and dark CSS variables, 4px spacing rhythm, 8–16px radii, restrained borders/shadow, focus rings, and breakpoints at 1020px, 860px, and 600px.
- [ ] Serve with `python -m http.server 4173 --directory design-preview` and verify `/` and `/styles.css` return HTTP 200.
- [ ] Render screenshots at 1440×1200 and 390×844; confirm no overlap or horizontal clipping.

### Task 3: Regression and Commit

**Files:**
- Verify: `design-preview/`
- Commit: this plan and all preview files

**Interfaces:**
- Produces: a reviewable implementation commit on the feature branch

- [ ] Run `uv run pytest -q`; expect every unit test to pass and hardware tests to remain excluded.
- [ ] Run `git diff --check`; expect no whitespace errors.
- [ ] Stage only the preview and plan files and commit as `feat: add GUI design system preview`.
