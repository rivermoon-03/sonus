# XM6 Official Product Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CSS headset illustration in the Sonus preview with a locally stored official Sony WH-1000XM6 black product image.

**Architecture:** The official PNG lives under `design-preview/assets/` and is referenced by semantic HTML. CSS controls containment and responsive sizing while preserving the existing status-panel layout; a Node test validates the asset signature, dimensions, and accessible markup.

**Tech Stack:** Official Sony PNG, HTML5, CSS, Node.js built-in test runner

## Global Constraints

- Use only an image sourced from an official Sony product page.
- Store the image locally instead of hotlinking it at runtime.
- Preserve the current light/dark themes, status content, and responsive layout.
- Include accessible alt text and visible source attribution.

---

### Task 1: Asset Contract

**Files:**
- Create: `design-preview/asset.test.mjs`

**Interfaces:**
- Consumes: `design-preview/assets/wh-1000xm6-black.png` and `design-preview/index.html`
- Produces: an executable contract for a valid, sufficiently large PNG and accessible product-image markup

- [ ] Write a Node test that checks the PNG signature, parses IHDR width and height as at least 400px, and confirms the HTML contains an image with descriptive WH-1000XM6 black alt text and an official Sony source link.
- [ ] Run `node --test design-preview/asset.test.mjs`; expect failure because the official image asset is absent.

### Task 2: Official Product Image

**Files:**
- Create: `design-preview/assets/wh-1000xm6-black.png`
- Create: `design-preview/assets/README.md`
- Modify: `design-preview/index.html`
- Modify: `design-preview/styles.css`

**Interfaces:**
- Consumes: the official Sony product PNG and Task 1 contract
- Produces: the real-product rendering inside `.device-visual`

- [ ] Download the black front-view WH-1000XM6 PNG from the official Sony product catalog URL into the assets directory.
- [ ] Record the official product page and direct asset URL in `assets/README.md`, noting that Sony owns the product image.
- [ ] Replace `.headband` and `.earcup` markup with an `<img>` and a compact linked source caption.
- [ ] Replace illustration CSS with `object-fit: contain`, responsive sizing, and a restrained shadow that works in both themes.
- [ ] Run `node --test design-preview/asset.test.mjs design-preview/app.test.mjs`; expect all tests to pass.

### Task 3: Render and Regression Verification

**Files:**
- Verify: `design-preview/`

**Interfaces:**
- Produces: desktop/mobile render evidence and a reviewable implementation commit

- [ ] Render at 1440×1200 and 390×844 from the local preview server and inspect for clipping or overlap.
- [ ] Run `uv run pytest -q`, `node --check design-preview/app.js`, and `git diff --check`; expect zero failures.
- [ ] Stage the image, attribution, HTML, CSS, test, and this plan; commit as `feat: use official XM6 product image`.
