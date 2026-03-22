# How tariff-everywhere Came Together

When I started exploring the US International Trade Commission's API, I was honestly just trying to understand what was there. The public endpoint was less documented than I expected, and the original plan I'd sketched referenced an endpoint that no longer worked. That initial confusion actually shaped everything that came after.

The real API turned out to be simpler than I'd feared: a flat JSON feed returning about 28,750 tariff entries across 99 chapters. No pagination helpers, no release versioning, just straightforward data. I realized that a chapter-based ingest pattern would work well—download one chapter at a time, parse it, store it. It's a pattern that scales linearly and gives you natural checkpoints.

I documented this learning in those early commits because I knew future me would forget the dead ends. The discovery phase isn't flashy work, but it's work that matters. You can't build something solid without understanding what you're actually building with.

---

## Building Three Layers

Once I understood the API shape, I needed to figure out how to make this thing actually useful. I wanted it to work in three different contexts: from the command line for developers, as an MCP server for Claude, and eventually as a browsable interface. But first things first—I had to build the foundation.

The ingest script was straightforward: hit the API for all 99 chapters, parse the JSON, and store everything in SQLite. I created three tables—chapters, hts_entries, and data_freshness—to capture both the tariff data and some metadata about when things were last checked. About 134,000 entries in total. It's a lot of data, but SQLite handles it fine.

The CLI came next. I used Typer because I'd worked with it before and it just gets out of the way. Commands for searching by keyword, looking up exact codes, browsing by chapter, getting metadata. Then an MCP server that exposed the same queries over stdio for Claude integration. The MCP work taught me something about JSON handling—I learned from Claude that using `print()` directly instead of Rich's console formatting keeps ANSI control characters out of the JSON output. It's a small detail, but it matters for integration.

Tests were important here too. I built the test suite early, using in-memory SQLite fixtures so tests run fast and don't depend on the actual database state. That pattern paid off immediately when refactoring came later.

---

## The Freshness Problem

After the initial ingest worked, I started thinking about what happens when tariff data changes. The USITC doesn't expose revision numbers or release dates, so I needed another way to know if the data is stale. This is where the idea of content hashing came in—hash each chapter, compare against what we've got stored, and only re-ingest if something actually changed.

I built the refresh script to do this in parallel. It spins up a thread pool, hashes all 99 chapters at once, and compares hashes to what's in the database. If a chapter's content is different, we re-ingest that chapter. I also started tracking two timestamps per chapter: when we last checked, and when it actually changed. That distinction matters—it tells you whether something is truly stale or just old data you've already validated.

Before any refresh operation, the script creates a backup. It's a simple thing, but it means if something goes wrong, we can recover. I've learned that defensive programming isn't paranoia—it's just respecting that production systems have higher stakes than development. The backup costs almost nothing and buys a lot of peace of mind.

This is where I learned to distinguish between ingest and refresh. Ingest is destructive—it rebuilds everything from scratch. Refresh is careful—it validates, updates selectively, and preserves the database. They're different operations with different failure modes, and treating them as such made the system safer.

---

## Stopping to Refactor

At some point, I noticed I was duplicating query logic between the CLI and the MCP server. Both needed to do the same database operations, just with different invocation patterns. This bothered me more than it should have, so I stopped feature work and extracted a shared core library.

Creating `hts_core/` with a configurable database path meant both interfaces could import the same functions. The CLI and MCP server both use it now, and when I need to change how queries work, I change them once. It's one of those refactorings that seems optional until you need to update something three months later and realize how grateful you should have been to past you.

I also hardened the Docker setup and added CI. The Dockerfile is lean—just what's needed, running as a non-root user. GitHub Actions runs the test suite on every commit. It's all pretty standard stuff, but it's the kind of thing that matters when you want people to trust what you've built. You're saying: this code doesn't just work on my machine, it works reliably, and if it breaks I'll know immediately.

These two things—the refactor and the CI setup—aren't glamorous work. But they're the difference between a spike that works and a project that actually stays working.

---

## The Datasette Pivot

Claude suggested something that changed how I thought about this project: "What if we exposed this as a searchable web interface?" I'd been thinking CLI and MCP only, but that suggestion opened something up. Why shouldn't people be able to browse tariffs in a browser?

That's how I ended up building Datasette integration. Datasette is remarkable because it lets you publish a SQLite database as a web interface without writing any web code. You just point it at your database, and suddenly you have a searchable, browsable interface with full-text search on tariff descriptions. No Flask routes, no HTML templates, no API endpoints to maintain.

The integration taught me some hard lessons about SQLite and Datasette. If you create FTS5 indexes with raw SQL, Datasette won't auto-detect them. But if you create them with `sqlite-utils`, Datasette sees them immediately. I learned that when I deployed the first version and search didn't work. I also ran into a Typer/click compatibility issue that took a minute to untangle.

Getting the chapter titles right was a small thing that mattered a lot. Instead of showing "Chapter 01," the interface now shows "Live Animals" or "Copper and Articles Thereof." It's more useful, and users see actual chapter names instead of numbers. Some entries have `<i>` tags for scientific names, and I had to install `datasette-render-html` to make those render correctly instead of showing raw HTML.

This pivot—from API-only to browsable web interface—is probably the thing I'm most proud of. It made the tariff data accessible to people who don't write code.

---

## Getting the Name Right

At some point it became clear that `usitc-app` was the wrong name. It was descriptive—it told you what API it used—but it didn't tell you what the project actually did or why you'd want to use it. I spent some time thinking about what this thing really was, and the name that emerged was `tariff-everywhere`. It's a lookup service you can use everywhere: in your terminal, in Claude, in a web browser. Anywhere you might need to understand a tariff code.

The rename was methodical. First the repository references, then the live web app URL, then the deployment configurations. I could have left some stray references to the old name, but that's the kind of thing that bugs future maintainers. If you're going to change something, change it all the way through.

---

## Documentation and Licensing

A project isn't really done until someone else can use it and maintain it. I spent time rewriting the README to guide people through the three different ways they could use tariff-everywhere: from the command line if they're a developer, as an MCP server if they're using Claude, or as a web interface if they just want to look something up. Each mode has its own documentation, and they're all starting from the same place.

CLAUDE.md became the deep documentation—here's the architecture, here are the patterns, here's how to debug when things go wrong, here's how to deploy. I did this because I know that future work on this project will probably involve Claude, and whoever touches the code next should understand the decisions that were made.

I also chose the Hippocratic License. It's an open-source license that protects against the code being used to cause harm. I wanted the code to be open—that's important to me—but I also wanted some guardrails. The Hippocratic License let me do both.

Licensing and documentation are the things people don't think about when they're building something, but they matter so much for longevity. A project without documentation dies. A project without thoughtful licensing can end up in places you never intended.

---

## Building With AI

The interesting thing about this project is that Claude wasn't added at the end—Claude was a thinking partner the whole way through. When I was confused about the API, Claude helped me understand what I was looking at. When I missed an ANSI control character vulnerability, Claude caught it. When I was stuck in a CLI-only mindset, Claude asked "what about a web interface?" and changed the whole trajectory of the project.

The later commits show preparing the repository for ongoing work with Claude. Adding `.claude/` to gitignore, documenting patterns and decisions in a way that makes sense to an AI reading the codebase. This isn't about "AI-assisted development" as a buzzword—it's about recognizing that I work better when I have someone smart to think with.

---

## What This Whole Thing Taught Me

**Defensive thinking matters.** Every feature I added, I asked "what goes wrong?" first. Backups before mutations. Hashes to detect changes. Tests that run in isolation. None of this is glamorous, but it's the difference between a project you can trust and one you can't.

**Refactoring when you spot duplication pays dividends.** The `hts_core/` extraction wasn't required, but it meant that later changes happened in one place instead of three. That matters.

**Naming is important.** `usitc-app` was technically correct and completely unmemorable. `tariff-everywhere` tells you what the project does and how it works. Spend the time on names.

**Three modes of interaction beat one.** A CLI is useful for developers. An MCP server is useful for Claude users. A web interface is useful for everyone else. The same underlying code, three different entry points. That's good design.

**Documentation is not optional.** Not because it's a checkbox, but because the next person to touch this code—including me, three months from now—needs to understand why decisions were made. CLAUDE.md isn't a reference manual, it's the paper trail of thinking.

---

## What Remains

The project is functional. All three modes work—CLI, MCP, web. Tests pass. The Datasette instance is live. The code is documented. The decisions are recorded. If I walked away today, someone could pick this up and maintain it. That feels complete.

What I've tried to do is leave the best gift a developer can leave: a codebase where decisions are explained, not just implemented. Where defensive patterns aren't random but intentional. Where someone—whether that's me in a few months or someone else entirely—can understand not just what the code does, but why it was built that way.

That's the real measure of a finished project.
