# Future Directions

Five paths forward for tariff-everywhere, evaluated through two lenses: **keep it tight** (low-overhead, agent-maintained) vs. **extend for impact** (reach new audiences). These aren't mutually exclusive — the first two directions strengthen the foundation; the latter three expand the surface area.

---

## 1. Autonomous Data Pipeline (Keep It Tight)

**What:** Make the system fully self-healing. Today's refresh workflow detects changes and opens an issue for manual review. Close that loop so tariff data stays current with zero human intervention, while preserving auditability.

**Concrete steps:**
- Auto-deploy on data changes: when `refresh-hts-data.yml` detects updated chapters, trigger `deploy-datasette.yml` automatically (with a diff summary committed to the repo for audit trail)
- Add a scheduled smoke test that hits the live Datasette instance and alerts if it's stale or down
- Track USITC data revision history over time — store snapshots or diffs so you can answer "what changed in Chapter 72 between March and June?"
- Use Claude Code scheduled agents to monitor for upstream API changes or breakage

**Why this matters:** The strongest version of this project is one you don't have to think about. It just works, stays current, and tells you when something interesting happens. This is also the most aligned with how you built it — Docker-first, CI-driven, no manual steps.

**Effort:** Low. Mostly workflow YAML and a small diffing script.

---

## 2. Comparative Tariff Intelligence (Extend for Impact)

**What:** Layer on data that turns raw HTS codes into actionable trade intelligence. The codes alone are a reference; combined with context, they become a decision-making tool.

**Possible layers:**
- **Country-specific rates:** Map HTS codes to actual applied rates by trading partner (MFN vs. preferential vs. retaliatory tariffs). The USITC General Notes and trade agreement annexes publish these, and recent executive orders (2025 tariff actions) make this urgently relevant.
- **Historical rate tracking:** Store rate snapshots over time so users can see "tariffs on steel from China went from 25% to 54% in Q1 2025" — the kind of thing driving the news stories that got you interested in the first place.
- **Product cost calculator:** Given an HTS code, country of origin, and declared value, estimate the landed cost including duty. This is the "starting a product business" use case — an importer entering a code and seeing real dollar impact.

**Why this matters:** This is where the data journalism and consumer education audiences show up. Raw tariff codes are arcane; "your $30 widget from Vietnam has a 12% duty" is immediately useful. It's also the clearest path from "reference tool" to "tool people recommend to each other."

**Effort:** Medium. Requires sourcing additional data (trade agreement rates, executive order modifications). The infrastructure is already there — new tables in SQLite, new CLI commands, new Datasette views.

---

## 3. Embeddable Widget / API (Extend for Impact)

**What:** Make tariff lookups embeddable in other people's tools. Today the data is accessible via CLI, MCP, and Datasette — all requiring the user to come to you. An embeddable widget or lightweight JSON API flips that.

**Forms this could take:**
- **Public JSON API:** Datasette already provides this (`/hts/hts_entries.json?hts_code=7408.11.30`), but it's not documented or marketed as an API. Add CORS headers, rate limiting, and a simple docs page.
- **Embeddable search widget:** A small JS snippet that sites can drop in to give their users tariff lookups. Think "powered by tariff-everywhere" at the bottom of an e-commerce product page or trade blog.
- **GitHub Action:** Let other repos query tariff data in their CI — useful for compliance checks in supply chain software.
- **MCP remote transport:** The MCP server currently runs locally via stdio. As MCP evolves toward streamable HTTP transport, the server could be deployed remotely alongside Datasette — giving AI agents direct access to tariff tools without requiring a local Docker container.

**Why this matters:** This is the multiplier. Every integration point means someone else's audience discovers the data. The MCP server already proves the concept — AI agents can use your tariff data. A public API extends that to any developer.

**Effort:** Low-to-medium. Datasette does most of the heavy lifting. The widget is a small frontend project. The main work is documentation and deciding on stability guarantees.

---

## 4. Guided Exploration for Non-Expert Users (Extend for Impact)

**What:** Build an interpretation layer for people who don't know what an HTS code is. The current Datasette UI is powerful but assumes familiarity with tariff classification. A guided experience could serve the "American consumer who heard about tariffs on the news" audience.

**What this looks like:**
- **Natural language search:** "shoes from Italy" instead of knowing to look at Chapter 64. The MCP server + Claude already enables this for AI-savvy users; a web frontend could democratize it.
- **Product-to-code mapper:** Start with a product category (electronics, clothing, food) and drill down visually through the HTS hierarchy. The `indent` field already encodes this tree structure.
- **"What does this tariff mean for me?" explainer:** Given a code and rate, generate a plain-English explanation of what products are covered, what the duty means in practice, and whether any exemptions or trade agreements apply.

**Why this matters:** This is the maximum-reach version of the project. Data journalists would link to it. Consumers would bookmark it. It turns a developer tool into a public utility. It's also a compelling demo of what structured government data looks like when made genuinely accessible.

**Effort:** Medium-to-high. Requires a frontend (could be minimal — even a single-page app on top of the existing Datasette API). The AI interpretation layer is the novel part.

---

## 5. Trade Policy Observatory (Extend for Impact)

**What:** Use the refresh infrastructure you already built to monitor and report on trade policy changes as they happen. Instead of just keeping data current, actively surface what changed and why it matters.

**Components:**
- **Change feed:** RSS/Atom feed or GitHub Discussions thread that publishes whenever tariff rates change, with context ("Chapter 73: Iron and Steel articles — 47 entries modified")
- **Diff reports:** Human-readable summaries of what changed between refreshes. "New 25% tariff on HTS 8471.30 (laptops) effective March 2025" is a story; a database update is not.
- **Watchlists:** Let users subscribe to specific chapters or codes and get notified when rates change. A data journalist covering agriculture watches Chapters 01-24. A hardware startup watches Chapter 84-85.

**Why this matters:** This positions the project as infrastructure for trade policy awareness, not just a lookup tool. The daily refresh workflow is already 80% of the way there — it detects changes and creates issues. The gap is translating those technical signals into something meaningful for a broader audience.

**Effort:** Medium. The detection infrastructure exists. The new work is presentation (feed format, notification delivery) and editorial (generating useful summaries, possibly with Claude).

---

## Recommendation

If maintaining low overhead is the priority: **Direction 1** first (make the pipeline fully autonomous), then **Direction 5** (observatory) — it builds directly on the refresh infrastructure and creates ongoing value with minimal maintenance.

If maximizing impact is the priority: **Direction 2** (comparative intelligence) is the highest-leverage single addition — it transforms the project from "browse tariff codes" to "understand what tariffs mean for your business." Pair it with **Direction 4** (guided exploration) to reach the broadest audience.

Direction 3 (embeddable API) is worth doing regardless — it's low effort and makes everything else more useful by letting other tools build on your data.

---

## A Note on What You've Already Built

The architecture you have — Docker-first, SQLite-backed, four interfaces (CLI, MCP, library, Datasette), automated refresh with human-in-the-loop deploy — is genuinely well-suited for any of these directions. The data layer doesn't need to change. The CI/CD patterns extend naturally. And the MCP server means AI agents are already first-class consumers of this data, which is a head start most projects don't have.

The fact that this started as "I want to understand tariff codes better" and became a tool that could serve importers, journalists, and consumers is a sign that the underlying problem — government trade data is hard to access and harder to interpret — is real and underserved. These directions are about choosing which slice of that problem to solve next.
