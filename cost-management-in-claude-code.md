# Cost Management in Claude Code — A Complete, Practical Guide

*Covers the Claude Code CLI. Where a feature is Anthropic-API-only or Claude-Code-only, it's marked clearly so you don't apply the wrong advice to the wrong surface.*

*Accuracy note: every price, limit, and feature below was verified against Anthropic's own documentation on 26 July 2026. A few facts in this space change on a fixed date (flagged inline) or drift with weekly Claude Code releases (also flagged). Re-check the linked source before relying on a number that matters to you.*

---

## Table of Contents

1. [What Is Cost Management in Claude?](#1-what-is-cost-management-in-claude)
2. [Everything You Have In Your Hands: The Full Toolkit](#2-everything-you-have-in-your-hands-the-full-toolkit)
3. [Model Selection](#3-model-selection)
4. [Context Management](#4-context-management)
5. [Prompt Caching](#5-prompt-caching)
6. [Reasoning / Effort Control](#6-reasoning--effort-control)
7. [Output Token Control](#7-output-token-control)
8. [Tool Use & MCP Costs](#8-tool-use--mcp-costs)
9. [Agentic Workflows, Subagents & Turn Limits](#9-agentic-workflows-subagents--turn-limits)
10. [Batch Processing (API only)](#10-batch-processing-api-only)
11. [RAG & Response Caching (build-your-own-app concerns)](#11-rag--response-caching-build-your-own-app-concerns)
12. [Observability — Watching Your Own Usage](#12-observability--watching-your-own-usage)
13. [Governance — Budgets, Limits & Policy](#13-governance--budgets-limits--policy)
14. [Our Enhancement: Statusline + handoff.md](#14-our-enhancement-statusline--handoffmd)
15. [Decision Framework — Which Action, When](#15-decision-framework--which-action-when)
16. [FAQ](#16-faq)
17. [Checklist](#17-checklist)
18. [References & Further Reading](#18-references--further-reading)

---

## 1. What Is Cost Management in Claude?

### 1.1 The simple answer

Cost management is the set of choices you make — which model, how much conversation history, whether to reuse work instead of redoing it — that decide how many tokens get processed to accomplish a task, and therefore how much that task costs.

That's it. There's no separate "cost mode" to turn on. Every lever in this article is something you're already touching — which model you pick, when you clear a conversation, whether caching is on — just looked at through the lens of "what does this cost."

### 1.2 The one mechanic that explains almost everything

If you remember a single fact from this article, make it this one:

> **In a conversational or agentic session, the entire conversation so far is re-sent as input on every single turn.**

Nothing is remembered between turns the way a human remembers a conversation. Claude has no memory of turn 1 while processing turn 20 — instead, the *entire* transcript of turns 1 through 19 is sent again, in full, as part of the input for turn 20. Your one-line question at 4pm pays for everything said since you opened the session that morning.

This explains almost every cost phenomenon in this guide:

- **Why cost grows faster than task length.** If each turn adds a fixed amount to the conversation, the total tokens *processed across the whole session* grows roughly with the square of the number of turns, not linearly. Twice the turns isn't twice the cost — it's closer to four times. (Worked example in [Section 9](#9-agentic-workflows-subagents--turn-limits).)
- **Why prompt caching saves so much.** If the same growing prefix is resent every turn, and the model can skip reprocessing the part it's already seen, that's the single biggest lever available — see [Section 5](#5-prompt-caching).
- **Why `/clear` is nearly free and `/compact` is not.** `/clear` deletes the thing that was about to be resent. `/compact` has to *read* that whole thing first, in order to summarize it.
- **Why a subagent that reads a huge file back is cheap.** The huge file lives in the subagent's *own* separate conversation, not yours — it never gets added to the thing that's resent on every one of your future turns.

Keep this one fact in mind and most of the rest of this article will feel like common sense rather than a list of rules to memorize.

📚 **Know more:** Anthropic's own writeup on this exact mechanic — [Effective context engineering for AI agents](https://claude.com/blog/context-management)

### 1.3 Two different "costs" — don't mix them up

Before any specific technique, one distinction matters more than any single tip in this article:

| | **Subscription (Pro / Max / Team / Enterprise seat)** | **API / Console (pay-per-token)** |
|---|---|---|
| You pay | A flat monthly fee | For every token processed |
| Your limit | A rolling **5-hour** usage window, plus a **weekly** cap | No usage window — spend is uncapped unless you set one |
| What "optimizing cost" buys you | **More work inside the same window** — you don't get money back | **A lower invoice**, directly |
| Where you see this | `claude.ai`, the `claude` CLI on a subscription login | Console dashboard, Anthropic API billing |

If you're on Pro or Max, nothing in this article lowers your bill — it's already fixed. What it *does* do is let you get more done before you hit your 5-hour or weekly ceiling, which is valuable, just a different kind of valuable than "cheaper."

If you're paying per token — a Console API key, Claude Code billed through a workspace, Bedrock, Google Cloud, or Microsoft Foundry — every technique below has a direct dollar effect.

This article is written to be useful either way, but keep track of which lane you're in, because "will this save money" has a different literal answer depending on it.

📚 **Know more:** [Claude plans & pricing](https://claude.com/pricing) · [Managing costs effectively in Claude Code](https://code.claude.com/docs/en/costs)

---

## 2. Everything You Have In Your Hands: The Full Toolkit

Before the detail, the whole map in one table. Every row gets its own section below.

| # | Lever | One-line summary | Where it lives |
|---|---|---|---|
| 3 | **Model selection** | Up to 10x price difference for the same task | Both |
| 4 | **Context management** | `/clear`, `/compact`, `CLAUDE.md`, skills — controlling what gets resent | Mostly CLI |
| 5 | **Prompt caching** | Reuse processed context at ~1/10th price instead of reprocessing it | Both (on by default) |
| 6 | **Effort / reasoning control** | How hard the model thinks before answering | Both |
| 7 | **Output token control** | Output costs 5x input on every current model | Both |
| 8 | **Tool use & MCP** | Tool definitions and results add tokens; some tools bill separately | Both |
| 9 | **Agentic workflows & subagents** | Turn count, subagents, and turn/budget caps | Mostly CLI |
| 10 | **Batch processing** | 50% off for asynchronous, non-interactive work | API only |
| 11 | **RAG & response caching** | Retrieval quality and reuse, if you're building an app on the API | API / app-layer |
| 12 | **Observability** | Tracking what you're actually spending, and on what | Both |
| 13 | **Governance** | Budgets, rate limits, and policy for teams | Both, heavier on Enterprise |
| 14 | **Statusline + handoff.md** | Our enhancement: see the numbers above live, and hand off cleanly | CLI |

A short honesty note before diving in: rows 3–9 and 12 are where almost all of your actual leverage lives if you're using the Claude Code CLI day to day. Rows 10 and 11 matter enormously if you're *building* something on the API, and barely apply to interactive CLI use at all — they're included because this article promises to cover everything, not because you should spend equal attention on them. Row 13 matters mostly once more than one person is involved.

---

## 3. Model Selection

### What it is, simply

Anthropic doesn't sell one model — it sells a family, and the cheapest and most expensive members of that family can differ in price by **10x** for the same request. Picking the right one for each task is the single highest-leverage decision in this entire article, and the easiest one to get wrong by just never revisiting a default.

### The current lineup (verified 26 July 2026)

| Model | Input ($/MTok) | Output ($/MTok) | Best for |
|---|---|---|---|
| **Haiku 4.5** | $1 | $5 | Classification, extraction, formatting, routing, simple search |
| **Sonnet 5** *(intro pricing to 31 Aug 2026)* | $2 → $3 after | $10 → $15 after | The production default for coding and everyday agent work |
| **Opus 5** *(current flagship)* | $5 | $25 | Architecture, hard debugging, long-horizon multi-step tasks |
| **Fable 5** | $10 | $50 | Tasks "larger than a single sitting" — not a default anywhere |

*(MTok = one million tokens. "Intro pricing" is a real, time-limited promotion — see the caveat below.)*

**⚠️ Time-sensitive fact:** Sonnet 5's lower price ($2/$10) is an introductory rate that **ends 31 August 2026**, after which it becomes $3/$15. If you're reading this after that date, halve the savings in any Sonnet-based example in this article. [Verify current pricing here.](https://platform.claude.com/docs/en/about-claude/pricing)

### Why the spread is this large

More capable models aren't just "smarter" — they're built and run differently, and that costs more per token to serve. Anthropic prices the family so you pay for exactly the amount of capability a task needs, rather than paying flagship prices for a task a cheap model handles just as well.

### How to choose in practice

Think of it as three buckets, not a spectrum:

- **Mechanical work → Haiku.** If a competent junior developer could do it by following a checklist — classify this ticket, extract this field, format this file — Haiku does it just as well as Opus, at a fifth of the price.
- **Normal development work → Sonnet.** This is the right default for most coding sessions. Anthropic positions it as approaching Opus-level quality on typical tasks at roughly a third of the cost.
- **Hard, ambiguous, high-stakes work → Opus.** Reach for it deliberately — a tricky architectural decision, a bug that's resisted three attempts, a large migration — rather than leaving it as your always-on default.

### Doing this automatically in Claude Code

You don't have to manually switch every time. Claude Code has real support for exactly this pattern:

- **`opusplan`** — uses Opus while you're in plan mode (thinking through the approach), then automatically switches to Sonnet to execute it. This is the cleanest version of "spend on thinking, save on typing."
- **`--advisor opus`** — keeps a cheaper model as the main driver, but lets it consult a stronger model at key decision points, instead of switching wholesale.
- **Per-subagent models** — a subagent frontmatter can pin `model: haiku`, so mechanical delegated work (like codebase search) never runs on your expensive session model by default. More in [Section 9](#9-agentic-workflows-subagents--turn-limits).

### A concrete number

Same workload — 100,000 requests a month, each with 3,000 input and 500 output tokens:

| Model | Monthly cost | vs. Haiku |
|---|---|---|
| Haiku 4.5 | $550 | 1x |
| Sonnet 5 (current intro price) | $1,100 | 2x |
| Opus 5 | $2,750 | 5x |
| Fable 5 | $5,500 | 10x |

Routing even 40% of a workload like this to Haiku, while keeping the rest on a stronger model, is worth roughly $880/month here — with no infrastructure change, just a routing decision.

### Caveat

Every current-generation model (4.7 and later — this includes Sonnet 5, Opus 5, and Fable 5) uses a newer tokenizer that produces **roughly 30% more tokens for the same text** than older models did. If you're comparing cost before and after upgrading models, re-measure cost-per-task rather than trusting the headline per-token price alone — a "same price" upgrade can still raise your bill.

📚 **Know more:** [Current models & pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [Choosing a model and effort level in Claude Code](https://claude.com/blog/claude-model-and-effort-level-in-claude-code)

---

## 4. Context Management

### What it is, simply

Context management is deciding what stays in the conversation that gets resent on every turn, and what gets removed, summarized, or never added in the first place. Since [Section 1.2](#12-the-one-mechanic-that-explains-almost-everything) established that the whole conversation is resent every time, this is really the practice of keeping that resent conversation as small and as *useful* as possible — those are two different goals, and the tools below split cleanly between them.

### The context window, in current numbers

| Where you're running | Context size |
|---|---|
| Claude Code on Pro or Team (Standard seat) | 200K tokens |
| Claude Code on Max / Team Premium / Enterprise | Up to 1M tokens (on the account's default model) |
| Anthropic API directly (Sonnet 5, Opus 5, Fable 5) | 1M tokens, standard pricing throughout |

A useful thing to know: on current models, there's no separate "long context surcharge." A 900,000-token request costs the same *per token* as a 9,000-token one. The size itself isn't the expense — what's inside it is.

### The core commands

| Command | What it does | Cost | Use it when |
|---|---|---|---|
| **`/clear`** | Wipes the conversation completely | **Free** | Moving to an unrelated task |
| **`/compact [instructions]`** | Replaces history with a structured summary | Costs a full read of the conversation being summarized | Continuing the *same* task, but the session has grown large |
| **`/rewind`** | Truncates back to an earlier point in the conversation | Cheap — returns to an already-processed point | Abandoning a path you started down |
| **`/recap`** | Adds a summary as new output, without deleting anything | Small, additive | You want a refresher without losing detail |

The single most common mistake: reaching for `/compact` as a general "tidy up" habit. `/compact` has to *read the entire conversation* in order to summarize it — it is not a cheap action, it's one of the more expensive single requests you can make. Running it every few turns "just in case" typically costs more than letting the conversation grow a bit longer and compacting once, deliberately, at a real boundary.

A full worked decision framework for exactly when to use which of these is in [Section 15](#15-decision-framework--which-action-when) — that section is designed to be read on its own if you just want the "which command, right now" answer.

### What survives `/compact`, and what doesn't

This trips people up, so it's worth a table:

| This survives | This doesn't (until re-triggered) |
|---|---|
| Project-root `CLAUDE.md` | Nested `CLAUDE.md` in subdirectories |
| Skills you actually invoked (truncated, see below) | Skills you never invoked — their descriptions aren't re-added either |
| Auto-generated memory | Path-scoped rules (`paths:` frontmatter) |

### `CLAUDE.md` — your project's standing instructions

`CLAUDE.md` is a file Claude Code reads at the start of every session and re-injects after every compaction. It's the right place for things that are permanently true about the project: build commands, architectural conventions, things Claude keeps getting wrong without being told.

**Anthropic's own guidance: keep it under 200 lines.** It loads on every single session whether you need it that turn or not, so it should hold only what's *always* relevant. Move anything workflow-specific — "how we do a release," "how we debug the auth service" — into a **skill** instead, which loads only when invoked.

One subtlety worth knowing: editing `CLAUDE.md` mid-session doesn't take effect until the next `/clear`, `/compact`, or restart. It's read once at session start, not watched for changes.

### Skills — instructions that cost nothing until used

A skill is a packaged set of instructions (a `SKILL.md` file) that only enters context when it's actually invoked — either by name (`/my-skill`) or, if allowed, by Claude deciding it's relevant. This is the mechanism that lets you keep detailed, specialized knowledge available without paying for it on every turn.

If a skill's body survives a compaction, it's capped at **5,000 tokens** (25,000 total across all invoked skills), and truncation keeps the *start* of the file. Put the important instructions first.

### RAG vs. sending the whole document — a quick rule of thumb

If you're building something that pulls from a large set of documents (this is more of an API/application concern than a day-to-day CLI one — see [Section 11](#11-rag--response-caching-build-your-own-app-concerns) for the fuller version): a document that's **stable and reused often** is usually cheaper to send in full and cache than to retrieve piecemeal, because a cached read costs a tenth of fresh input. A document set that's **large with each request needing a different small slice** favors retrieval. When in doubt, the deciding factor is usually retrieval *quality* — a cheap-but-mediocre retrieval that forces a follow-up turn costs more than the tokens it saved.

📚 **Know more:** [Claude Code — explore the context window](https://code.claude.com/docs/en/context-window) · [How Claude remembers your project](https://code.claude.com/docs/en/memory) · [Context editing (API)](https://platform.claude.com/docs/en/build-with-claude/context-editing)

---

## 5. Prompt Caching

### What it is, simply

Prompt caching lets you pay a small fee to "remember" a chunk of context, so that resending it on a later turn costs a tenth of the normal price instead of the full price. Given that the entire conversation is resent every turn ([Section 1.2](#12-the-one-mechanic-that-explains-almost-everything)), this is the single biggest lever in this whole article — and the good news is it's **on by default** in Claude Code. Your job is mostly to avoid accidentally breaking it.

### How it actually works

Anthropic's systems match the **beginning** of your request against something it processed recently. The match only works from the start forward: if anything changes partway through, everything *after* that change has to be reprocessed, even if the rest was identical. This is why Claude Code deliberately puts the most stable content first (system prompt, then project instructions, then the actual back-and-forth), and why doing something that changes the stable part — like switching models — is expensive.

### Current pricing multipliers

| Action | Price vs. normal input | Notes |
|---|---|---|
| Writing to a 5-minute cache | 1.25x | Pays for itself after just **1** read |
| Writing to a 1-hour cache | 2x | Pays for itself after **2** reads |
| Reading from cache (a "hit") | **0.1x** | This is the whole point |

On a Claude subscription, Claude Code automatically requests the 1-hour cache — it costs you nothing extra since usage is already included in your plan, and it just keeps things warm longer. On an API key, the 1-hour option is opt-in.

### The minimum size to actually get cached

Below a certain size, a request is cached... **exactly not at all, with no error and no warning.** This is the single most common way people think caching is working when it isn't.

| Model | Minimum prompt size to cache |
|---|---|
| Opus 5, Fable 5 | 512 tokens |
| Sonnet 5, Opus 4.8 | 1,024 tokens |

If your prompts are short and you're not seeing savings, this is almost always why.

### What breaks the cache — the practical list

| Breaks it | Doesn't break it |
|---|---|
| Switching models mid-session (each has its own cache) | Editing repository files |
| An MCP server connecting or disconnecting | Editing `CLAUDE.md` (takes effect at next reload anyway) |
| A Claude Code version upgrade mid-session | Changing output style |
| `/compact` (by design — it's summarizing) | Invoking a skill |
| Adding a broad tool-deny rule mid-session (e.g. blocking `Bash` entirely) | Spawning a subagent |

The upgrade point is worth calling out specifically: resuming a long session right after upgrading Claude Code reprocesses the *entire* history with zero cache hits. If a session matters, finish or checkpoint it before upgrading.

### A concrete number

A 20-turn Claude Code session with a stable ~60,000-token prefix (system prompt + project instructions + accumulated history), one turn roughly every two minutes, on Opus 5:

| | Cost |
|---|---|
| No caching (hypothetically) | $6.00 |
| With 5-minute caching | **$0.95** (84% less) |
| With 1-hour caching | **$1.17** |

The 1-hour option costs slightly more up front but wins whenever gaps between turns regularly exceed 5 minutes, since the shorter cache would otherwise expire and force a full, expensive rebuild.

### Caveat

Turning caching off is almost never the right call in production — it exists as a debugging toggle, not a real setting to consider changing day to day.

📚 **Know more:** [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [How Claude Code uses prompt caching](https://code.claude.com/docs/en/prompt-caching) · [Lessons from building Claude Code: prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything)

---

## 6. Reasoning / Effort Control

### What it is, simply

Current Claude models can think before they answer, and "effort" is the dial that controls how much thinking they do. More effort generally means better answers on hard problems, but the thinking itself is billed as **output tokens** — often the majority of them on a hard question — so this dial has a large and direct effect on cost.

### The levels

| Level | When it's the right choice |
|---|---|
| `low` | Short, well-scoped, latency-sensitive requests |
| `medium` | Most cost-sensitive work that can trade a little intelligence for savings — this is the main lever |
| `high` | The default. A reasonable balance for most tasks |
| `xhigh` | Genuinely hard coding or multi-step agentic work |
| `max` | No constraint at all — prone to overthinking; test before adopting broadly |

An important detail: the scale is **calibrated per model**, not absolute. Anthropic notes that Sonnet 5 at `medium` performs comparably to an older model at `high` — so "medium" doesn't mean the same thing on every model, and it's worth testing on your own tasks rather than assuming.

### How to set it

`/effort` inside a Claude Code session, a `--effort` flag at launch, or a per-skill / per-subagent setting in frontmatter for finer control than one blanket session-wide level.

### Cost impact, made concrete

Same 50,000-token input request on Opus 5, at three different effort/output outcomes:

| Scenario | Output tokens | Total cost |
|---|---|---|
| Concise answer | 500 | $0.26 |
| Normal answer | 2,000 | $0.30 |
| `max` effort, long reasoning | 20,000 | $0.75 |

The input side of this request barely changes. Effort level — how much the model thinks and writes — is what moves the price.

### Caveat

Effort is **not part of the cache key** — changing it mid-session does not invalidate your prompt cache the way switching *models* does. That makes it a genuinely low-risk lever to experiment with, compared to most of the others in this article.

📚 **Know more:** [Effort](https://platform.claude.com/docs/en/build-with-claude/effort) · [Choosing a model and effort level in Claude Code](https://claude.com/blog/claude-model-and-effort-level-in-claude-code)

---

## 7. Output Token Control

### What it is, simply

Every current Claude model prices output tokens at **5 times** the rate of input tokens. A response that's twice as long as it needed to be isn't a small inefficiency — it's the most expensive kind of token you can generate, generated in double the quantity.

### Why this catches people off guard

Thinking tokens (from [Section 6](#6-reasoning--effort-control)) are billed as output too, and they don't visually look like "the answer" the way normal response text does. A verbose reasoning process can quietly dominate a request's cost even when the final visible answer is short.

### The controls that actually exist

| Control | What it does |
|---|---|
| `max_tokens` | A hard ceiling on output — **thinking plus response text combined**, not response text alone |
| Structured output (JSON schema) | Forces a specific shape, which is naturally shorter and easier to parse than free text |
| Concise prompting | Works better as **positive examples** of the length/style you want than as "don't be verbose" instructions |
| Effort level | The primary lever for output *volume* on reasoning-capable models — see [Section 6](#6-reasoning--effort-control) |

### The rule of thumb that matters more than any single technique

Don't optimize output length in a way that increases how many turns a task takes. If trimming a response by 500 tokens causes a follow-up question that costs another full turn — remember, that follow-up turn resends the *entire* conversation — you've made things worse, not better. Shorter is only cheaper when it doesn't cost you a turn.

📚 **Know more:** [Prompting Claude Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5) · [Pricing (see output multipliers)](https://platform.claude.com/docs/en/about-claude/pricing)

---

## 8. Tool Use & MCP Costs

### What it is, simply

Every tool you give Claude access to — file editing, bash, web search, an MCP server — adds tokens in two separate ways: the **definition** of the tool (sitting in your system prompt, on every turn) and the **results** the tool returns (added to the conversation, and therefore resent on every subsequent turn too).

### Definitions aren't free, but they're usually small

A bash tool or text editor definition adds a few hundred tokens to every request. That's a rounding error on its own — the real cost is almost always in results, not definitions.

### MCP specifically — the CLI-relevant part

In Claude Code, MCP tool definitions are **deferred by default**: only the tool's *name* enters context (a tiny amount) until Claude actually decides to use it, at which point the full definition loads. This keeps idle MCP servers cheap to have connected.

The real cost of MCP isn't the tokens — **it's cache invalidation.** A server's process exiting, an HTTP session expiring, or an automatic reconnect changes the tool set mid-session, which invalidates your entire prompt cache exactly as covered in [Section 5](#5-prompt-caching). This can happen with no action on your part.

**Anthropic's own recommendation, worth repeating directly: prefer CLI tools over MCP servers where both exist.** Something like `gh` (GitHub's CLI) run via the Bash tool adds no per-tool listing at all, and doesn't carry the reconnect-invalidation risk an MCP server does.

### Server-side tools that bill separately

| Tool | Extra charge |
|---|---|
| **Web search** | $10 per 1,000 searches, regardless of result count |
| **Web fetch** | No extra charge — token cost only (a large page can still be a lot of tokens) |
| **Code execution** | Free when paired with recent web search/fetch tools; otherwise billed by container time after a daily free allowance |

A subtlety worth knowing: web search results become part of your conversation, so a handful of searches early in a session get resent — and paid for — on every later turn, just like anything else in context. The per-search fee is often the smaller part of the true cost.

### Reducing unnecessary tool calls

- Restrict the available tool set for a session or subagent to only what's needed.
- Use a **hook** to pre-filter verbose tool output before it reaches Claude at all — Anthropic's own example: instead of Claude reading a 10,000-line log to find an error, a hook greps for `ERROR` first and hands back only the matching lines. This is one of the highest-leverage, least-discussed techniques in this whole article.
- Judge a tool by **turns avoided**, not tokens added — a tool that saves you from a back-and-forth is almost always worth its small definition cost.

📚 **Know more:** [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp) · [Hooks reference](https://code.claude.com/docs/en/hooks) · [Tool use with prompt caching](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching)

---

## 9. Agentic Workflows, Subagents & Turn Limits

### What it is, simply

An "agentic" session — Claude working through a multi-step task, running commands, checking results, adjusting — is really just a very long conversation with itself. Every mechanic from [Section 1.2](#12-the-one-mechanic-that-explains-almost-everything) still applies, which means agent cost grows in a specific, predictable, and easy-to-underestimate way.

### Why agent cost is quadratic, not linear

If every turn adds roughly the same amount to the conversation, and every turn resends everything before it, then the *total* tokens processed across an N-turn session grows with roughly N², not N. Going from 5 turns to 20 turns isn't 4x the work — it's closer to 7–8x the cost.

**Worked example, Opus 5, a session that grows by ~5,000 tokens per turn:**

| Turns | Total tokens processed (uncached) | Cost (uncached) | Cost (with caching) |
|---|---|---|---|
| 5 | 175,000 | $1.06 | ~$0.41 |
| 10 | 475,000 | $2.75 | ~$0.89 |
| 20 | 1,450,000 | $8.00 | ~$2.21 |

**4x the turns (5 → 20) produced 7.5x the cost.** This is the single most important number in this whole article for anyone running agentic sessions regularly. It's also *why* `--max-turns`, plan mode, and catching a wrong approach early are cost controls, not just quality controls — every turn you avoid is worth disproportionately more than the last one suggests.

### Subagents — delegating without paying for the detour

A subagent runs in its own, separate conversation. It can read a huge file, run an exhaustive search, or churn through a long exploration — and only its final, short summary comes back into *your* conversation. The huge intermediate work never becomes part of what gets resent on your future turns.

Anthropic's own illustration: a research subagent read 6,100 tokens of files and returned a 420-token summary. If that same reading had happened directly in your main conversation, all 6,100 tokens would be sitting there, getting resent, on every turn from then on.

**Practical use:**
- Delegate anything verbose (test runs, log parsing, broad codebase search) to a subagent instead of doing it inline.
- Pin cheap subagents to Haiku (`model: haiku` in frontmatter) — exploration and search rarely need a stronger model.
- The built-in `Explore` agent inherits your *session's* model by default. A project-level override naming a subagent `Explore` with `model: haiku` makes every exploration cheap without you having to remember to delegate manually. (This exact override is one of the two things our enhancement in [Section 14](#14-our-enhancement-statusline--handoffmd) ships as a ready-to-use template.)

### Turn and budget limits

| Control | What it does |
|---|---|
| `--max-turns N` | Caps how many turns an unattended/scripted run can take before stopping |
| `--max-budget-usd N` | A hard dollar cap on a single invocation — **subagent spending counts toward it** |
| Per-subagent `maxTurns` | Caps a specific subagent rather than the whole session |

For anything automated or unattended, `--max-budget-usd` is arguably the single most direct cost guardrail available in the CLI — it's a real dollar ceiling, not a proxy for one.

### Preventing wasted loops, without a flag

Some of the best cost control here isn't a setting at all:

- **Use plan mode before implementation** on anything non-trivial. If the plan is wrong, you find out *before* paying for a long edit-test-fix loop, not after.
- **Give Claude something to verify against** — a test, an expected output, a screenshot. When it can check its own work, it catches problems before spending a turn asking you.
- **Write specific prompts.** "Improve this codebase" invites broad, exploratory (expensive) scanning. "Add input validation to the login function in `auth.ts`" doesn't.

📚 **Know more:** [Create custom subagents](https://code.claude.com/docs/en/sub-agents) · [CLI reference](https://code.claude.com/docs/en/cli-reference) · [Managing costs effectively in Claude Code](https://code.claude.com/docs/en/costs)

---

## 10. Batch Processing (API only)

### What it is, simply

If you're building on the Anthropic API directly and can accept your results arriving within 24 hours instead of instantly, Batch gives you a flat **50% discount** on both input and output tokens, with no difference in answer quality — only in timing.

**This does not apply to interactive Claude Code sessions at all.** A live coding session is inherently real-time; there's no "batch mode" for a conversation you're having right now. This section exists for completeness and because Claude Code work sometimes sits alongside batch-eligible pipelines (nightly test sweeps, bulk doc processing) in the same team's toolkit.

### When it makes sense

Offline evaluations, nightly data enrichment, bulk classification or tagging, backfills, and any CI job where a few hours of latency genuinely doesn't matter.

### Can it combine with caching?

Yes — a shared instruction prefix across many batched requests can be cached, and the cache-read discount stacks with the batch discount, making an already-cheap path cheaper still.

📚 **Know more:** [Batch processing](https://platform.claude.com/docs/en/build-with-claude/batch-processing)

---

## 11. RAG & Response Caching (build-your-own-app concerns)

### What these are, simply

Both of these matter if you're **building an application** on top of the Claude API — they're largely irrelevant to using the Claude Code CLI day-to-day, which is why this section is short relative to the others.

**Retrieval-Augmented Generation (RAG)** means fetching only the relevant slice of a larger document set instead of sending everything. It's a cost lever, not just a relevance one: every irrelevant chunk you retrieve is paid for, on every turn it survives in context. Retrieving fewer, better-chosen chunks (sometimes with a cheap reranking pass in front of a stronger generation model) is usually both cheaper and higher quality than retrieving more.

**Response caching** is different from prompt caching, and the two get confused constantly:

| | Prompt caching | Response caching |
|---|---|---|
| Who builds it | Anthropic (built-in) | You (application layer) |
| What's reused | The processed input | The complete, final output |
| Best case | 1/10th the input price | **$0** — no model call at all |
| Risk | None | Real — a stale or wrong-context match returns a wrong answer |

Response caching (sometimes "semantic caching") makes sense for things like FAQ deflection or repeated identical questions from many users. It essentially never applies to a Claude Code session, since a coding session is stateful and specific to one repository at one moment — there's nothing to match a "cached response" against.

📚 **Know more:** [Context editing (API)](https://platform.claude.com/docs/en/build-with-claude/context-editing)

---

## 12. Observability — Watching Your Own Usage

### What it is, simply

Every technique above is a lever you can pull. Observability is how you find out whether pulling it actually did anything — without measurement, "I think that helped" is just a guess.

### Inside the CLI, right now

| Command | Shows you |
|---|---|
| **`/usage`** | Session token stats and a locally estimated dollar figure; on paid plans, attributes recent usage to specific skills, subagents, and MCP servers |
| **`/context`** | A live breakdown of what's occupying your context window, by category |
| **`/memory`** | Which `CLAUDE.md` and memory files actually loaded this session |

**Important caveat:** the dollar figure in `/usage` is computed **locally, at standard list rates** — it doesn't know about promotional pricing or any contracted discount, and on a subscription plan it is explicitly *not* what you're billed. Treat it as a relative signal ("this session cost more than that one"), never as a reconciliation against an actual invoice.

### The metrics worth actually tracking

| Metric | Why it matters |
|---|---|
| Cache hit rate (reads ÷ (reads + fresh writes)) | The single best health indicator for an agentic session — see [Section 5](#5-prompt-caching) |
| Model usage breakdown | Catches "we meant to use Sonnet but Opus was left as the default" |
| Turn / subagent count | The direct driver of the quadratic cost curve in [Section 9](#9-agentic-workflows-subagents--turn-limits) |
| **Cost per successful task**, not just cost per request | The only number that should actually drive a model or process decision — a cheaper request that fails and needs a retry isn't actually cheaper |

### For teams

Team and Enterprise plans expose a spend report broken down by user and model; API/Console usage has an equivalent dashboard; and for real-time, per-user metrics streamed into your own monitoring stack, Claude Code supports **OpenTelemetry** export, which works regardless of which billing surface you're on.

📚 **Know more:** [Monitoring usage (OpenTelemetry)](https://code.claude.com/docs/en/monitoring-usage) · [Track team usage with analytics](https://code.claude.com/docs/en/analytics) · [Usage and Cost Admin API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)

---

## 13. Governance — Budgets, Limits & Policy

### What it is, simply

Once more than one person is spending against the same account, "be careful" stops being a strategy. Governance is turning the individual habits in this article into something enforced rather than hoped for.

### The main controls

| Control | What it does | Where |
|---|---|---|
| Workspace spend limits | A hard cap on a Console workspace's spend | API/Console |
| Per-member usage credits & limits | Individual spend ceilings within a team | Team / Enterprise |
| `--max-budget-usd` | A hard cap on a single unattended run | CLI, any surface |
| `availableModels` + `enforceAvailableModels: true` | Restricts which models a user or session can select | CLI, managed settings |
| Organization effort limits | Caps the maximum effort level available per model/role | Enterprise |

**The most commonly missed setting here:** `availableModels` on its own does **not** constrain what happens when a user selects "Default" — without also setting `enforceAvailableModels: true`, someone can bypass your allowlist entirely just by picking the default option. If you're setting model restrictions for a team, both settings need to be present together.

### A practical rollout note

Anthropic's own guidance for teams adopting these controls: start with a small pilot group, measure a baseline with the observability tools in [Section 12](#12-observability--watching-your-own-usage), then expand — rather than writing a policy first and measuring after.

📚 **Know more:** [Claude Code model configuration](https://code.claude.com/docs/en/model-config) · [Rate limits](https://platform.claude.com/docs/en/api/rate-limits) · [Claude Enterprise consumption guide](https://support.claude.com/en/articles/14782391-claude-enterprise-consumption-guide)

---

## 14. Our Enhancement: Statusline + handoff.md

Everything in Sections 3–13 is something Claude Code and Anthropic already give you. This section is different: it's a small, concrete addition — built and tested while writing this article — that makes two of the most important numbers above actually *visible*, and makes the context-management habits in Section 4 automatic instead of remembered.

### 14.1 The problem this solves

Two things are true at the same time:

1. The most predictive cost metric — **cache hit rate** — is invisible by default. Claude Code's status line doesn't show it, and most people never check `/usage` mid-session.
2. The best context-management habit — write down state before clearing — is easy to *know* and easy to *forget*, especially under the pressure of a context window that's already nearly full.

The enhancement is one answer to each.

### 14.2 The statusline design

A status line that updates after every turn, showing exactly these fields, in this order:

```
Sonnet 5 │ #4 │ [█████████░] 89% │ 42.1k tok │ cache 97% │ $0.31 │ +$0.12
```

| Field | Meaning | Native Claude Code field, or derived? |
|---|---|---|
| **Model** | Which model is active right now | Native |
| **Prompt number** (`#4`) | How many turns into this session you are | **Derived** — see note below |
| **Context bar** | Visual + percentage of the context window used | Native |
| **Tokens this turn** (`42.1k tok`) | The input-token size of the most recent API call | Native (Claude Code's own field for this calculation) |
| **Cache hit rate** (`cache 97%`) | Share of this turn's input tokens served from cache instead of reprocessed | Derived from native fields |
| **Cumulative cost** (`$0.31`) | Running total for the session, at list-rate estimate | Native (with the same caveat as `/usage` in [Section 12](#12-observability--watching-your-own-usage)) |
| **Marginal cost** (`+$0.12`) | The cost of *just this turn* | **Derived** — see note below |

**Honesty note on the two derived fields:** Claude Code's status line only reports *cumulative* totals — total cost so far, total tokens so far. It has no native concept of "which turn number is this" or "what did just this turn cost." The script gets both by remembering the previous turn's cumulative totals in a small local state file and taking the difference. This is a real limitation worth stating plainly: it's an addition built *on top of* what Claude Code exposes, not a feature of Claude Code itself.

**Why prompt number and marginal cost, specifically:** the cumulative cost figure answers "how expensive has this session been so far" — useful, but it doesn't tell you whether the *last thing you just did* was cheap or expensive. A session can look fine in aggregate while one particular turn (a model switch, a huge file read, a cache rebuild) quietly did most of the damage. Marginal cost isolates that. Prompt number just gives you a stable reference to talk about it ("prompt #14 was the expensive one").

**A correctness detail that matters:** the status line can be asked to refresh on a timer, independent of whether a new turn actually happened. The script only advances the prompt counter and recomputes the marginal cost when the cumulative total has genuinely changed since the last time it ran — otherwise it redisplays the same numbers. Without this check, a timer-triggered refresh would look like a free extra turn, or worse, a turn that mysteriously cost $0.

**Reading the colors:** cache hit rate and context both use the same threshold logic — green is healthy, yellow means "keep an eye on it," red means "something's actively wrong, usually a rebuilt cache or a nearly-full window." A single red cache reading right after `/compact` or at session start is expected — that's precisely when the cache has nothing yet to hit. Red turn after turn is the actual signal.

### 14.3 The handoff.md design

`handoff.md` is a single, durable file that captures what a session knows, so that knowledge doesn't disappear when the conversation is cleared, the machine changes, or a different person picks up the work.

**What triggers writing one:** stopping for the day mid-task, handing off to a teammate, switching machines, or — tied directly to Section 4 — right before a `/compact` or `/clear` on any task complex enough that you don't trust an automatic summary to keep the right things.

**What goes in it**, and — importantly — **why each section exists**:

| Section | Contents | Why it's there |
|---|---|---|
| Goal | One or two sentences on what "done" looks like | Prevents "done" from silently drifting over a long task |
| Done / Next | Concrete, verifiable progress; the specific next action | So work resumes without re-deriving where it left off |
| **Decisions made — do not relitigate** | Approaches chosen *and* alternatives rejected, with a one-line reason each | **The highest-value section.** Anyone can read the code to see *what* was built. Nobody can read the code to see *why* a different approach was rejected — that reasoning exists only in this file |
| Open questions | Anything genuinely undecided | Keeps the next session honest instead of quietly assuming |
| Gotchas | Non-obvious things learned the hard way | Stops the next session from rediscovering the same surprise |

**Why a fixed filename instead of only timestamped snapshots:** a timestamped archive (`.claude/checkpoints/2026-07-26-1432-auth-fix.md`) is good history, but it requires knowing the timestamp to find the *latest* one. `handoff.md` at the project root is always the current one — a new session, a teammate opening the repo, or `/restore` can find it without knowing anything about when it was written. Both exist together: the timestamped file is the archive, `handoff.md` is the pointer to "now."

### 14.4 Where this fits into everything above

Neither piece is a new lever — they're an interface onto levers that already existed in this article:

| Enhancement piece | Makes visible / automatic... |
|---|---|
| Cache hit rate in the statusline | The health of [Section 5 — prompt caching](#5-prompt-caching), in real time instead of via a manual `/usage` check |
| Context bar in the statusline | The state that drives the [Section 4](#4-context-management) `/clear`-vs-`/compact` decision |
| Marginal cost in the statusline | Which specific turn triggered the [Section 9](#9-agentic-workflows-subagents--turn-limits) quadratic cost growth |
| `handoff.md` | The habit at the center of [Section 4](#4-context-management)'s "don't lose real state when you clear" advice, turned into a standing practice instead of a one-off |

Neither piece requires trusting a new mechanism — both are read-only observation (the statusline) or a plain markdown file you can open and read yourself (`handoff.md`). That's a deliberate choice: a cost-management tool that itself becomes an opaque cost or a new failure mode isn't a net win.

---

## 15. Decision Framework — Which Action, When

Every mechanism in this article eventually collapses into one repeated question:

> **Is what's in this conversation still useful for the next turn?**

| Your answer | Action | Section |
|---|---|---|
| Yes, all of it, same task | Keep going | — |
| Yes, but it's grown large | **`/compact <focus>`** | [§4](#4-context-management) |
| No, unrelated task starting | **`/clear`** | [§4](#4-context-management) |
| Some of it, but I'm stopping for real | **Write `handoff.md`, then `/clear`** | [§14](#14-our-enhancement-statusline--handoffmd) |
| No, and I don't trust what's here | **`/rewind`, or a fresh session** — not `/compact` | [§4](#4-context-management) |
| I want to continue a *previous* session later | **`/resume`** (see FAQ) | [§16](#16-faq) |

### The two mistakes worth avoiding specifically

**Using `/compact` when the problem is trust, not size.** If Claude has repeated the same wrong assumption two or three times, the fix isn't a summary — the wrong assumption is *in* the history, and `/compact` will summarize it faithfully right alongside everything correct. Use `/rewind` to a point before the mistake, or `/clear` and restate the problem cleanly.

**Using `/compact` out of habit rather than at a real boundary.** As covered in [Section 4](#4-context-management), `/compact` reads the whole conversation it's about to summarize — it's a genuinely expensive action, not a free "tidy up." Reserve it for moments the session is both large *and* worth continuing.

### When to start an entirely new session, not just `/clear`

`/clear` empties the conversation but keeps you in the same directory and process. Start a **new session** instead when you're switching repositories or worktrees (the prompt cache is scoped to one machine *and* one directory anyway, so there's no caching reason to stay), or when a session has run long enough that you're no longer confident what's still true in it.

---

## 16. FAQ

**What's the actual difference between `/clear`, `/compact`, `/rewind`, and writing a `handoff.md`?**

`/clear` deletes the conversation, free of cost. `/compact` replaces it with an AI-generated summary, at the cost of reading everything first. `/rewind` truncates back to an earlier point, cheaply, which is the right move when you're abandoning an approach rather than continuing one. `handoff.md` is different in kind from the other three — it's not a Claude Code command at all, it's a file *you* write (or have Claude write from context already in the conversation) that survives even a full `/clear`, a machine change, or a different person picking up the work. The first three manage what's inside one conversation; `handoff.md` is what persists after that conversation is gone.

**When should I use `/resume` instead of starting fresh or using `/clear`?**

`/resume` (or `claude --resume`) reloads a *previous* session's saved transcript on the same machine and continues from there — useful when you stepped away and want the exact prior conversation back, not a clean slate. Two things to know: since time has passed, the prompt cache from that old session has almost certainly expired (5 minutes to 1 hour depending on configuration — see [Section 5](#5-prompt-caching)), so the first turn after resuming reprocesses the whole history at full price, same as any cold start. And `/resume` only works on the machine that has that local transcript — it's not a handoff mechanism. If you need to move work to a different machine or person, `handoff.md` is the tool for that, not `/resume`.

**Is prompt caching something I need to turn on, or configure per request?**

No — it's on by default in Claude Code, and for most sessions you don't need to think about it at all. Where it becomes something to actively manage: (1) if your requests are shorter than the per-model minimum in [Section 5](#5-prompt-caching), caching silently doesn't apply and there's nothing to configure that fixes that — the request is just too small; (2) if you're switching models frequently mid-session, each switch starts a fresh cache, so caching is "on" but constantly restarting; (3) on a raw API key rather than a subscription, the 1-hour cache is opt-in rather than automatic.

**Which model should I actually default to?**

Sonnet, for the large majority of coding and everyday agent work — see [Section 3](#3-model-selection). Reach for Opus deliberately for hard, ambiguous, or high-stakes tasks, rather than leaving it as an always-on default. Haiku for anything mechanical enough that a checklist could describe it.

**Which effort level should I actually default to?**

The built-in default (`high`) is a reasonable choice to leave alone until you have a specific reason to change it. `medium` is worth testing deliberately on cost-sensitive, well-scoped work — see [Section 6](#6-reasoning--effort-control) — rather than assumed to be "worse" outright; Anthropic's own guidance notes newer models at `medium` can match older models at `high`.

**Does checkpointing / `handoff.md` replace good `CLAUDE.md` hygiene?**

No — they operate on different timescales. `CLAUDE.md` ([Section 4](#4-context-management)) holds things permanently true about the project. `handoff.md` holds the state of *one piece of work*, right now. If something written in a `handoff.md` turns out to be permanently true, it should graduate into `CLAUDE.md` — it shouldn't be left sitting only in a dated handoff file.

**How do I tell "context is poisoned" apart from "context is just large"?**

Large context: things still work, just more slowly and expensively. Poisoned context: the *same* mistake recurs after you've already corrected it once. Size is solved by `/compact`. Recurrence is not — the wrong assumption is sitting in the history that `/compact` would faithfully summarize. That calls for `/rewind` or a clean restart instead.

**Should `handoff.md` be committed to version control?**

If it's meant to make handoffs reviewable by a team — the more useful default — commit it. If it's genuinely personal scratch state, add it to `.gitignore`. Either way, it shouldn't live inside `CLAUDE.md` itself, since that file reloads every session and isn't meant for one task's dated notes.

**Do I need to manually track cache hit rate, or is the statusline enough?**

For day-to-day awareness, the statusline in [Section 14](#14-our-enhancement-statusline--handoffmd) is enough — that's exactly the gap it's built to close. For team-wide tracking across many sessions and people, use the observability tools in [Section 12](#12-observability--watching-your-own-usage) instead; the statusline is a single-session, single-glance tool, not an aggregate one.

**Is any of this relevant if I'm on a Pro or Max subscription rather than paying per token?**

Model choice, context management, and caching all still matter — they determine how much you can get done before hitting your rolling 5-hour or weekly usage window (see [Section 1.3](#13-two-different-costs--dont-mix-them-up)). What changes is that none of it lowers an invoice, because there isn't a per-token invoice to lower. Batch processing ([Section 10](#10-batch-processing-api-only)) and most of governance ([Section 13](#13-governance--budgets-limits--policy)) are the two areas that genuinely don't apply on a subscription.

---

## 17. Checklist

A condensed pass/fail list. Check these in order — the first few matter far more than the rest.

- [ ] **Model:** default is Sonnet, not Opus; nothing important still defaults to `max` effort
- [ ] **Context:** `/clear` between unrelated tasks; `/compact` only at real boundaries, with a focus instruction; `CLAUDE.md` under ~200 lines
- [ ] **Caching:** verified on (it's default); nothing under the per-model minimum size expecting a cache hit that won't happen; not switching models mid-task without reason
- [ ] **Effort:** tested `medium` on at least one real, cost-sensitive workload rather than assuming `high` is required
- [ ] **Output:** `max_tokens` set deliberately somewhere it matters; concise-by-example rather than concise-by-instruction
- [ ] **Tools/MCP:** unused MCP servers disconnected; CLI tools preferred where an equivalent exists; verbose command output filtered via a hook where it recurs
- [ ] **Agents:** verbose work delegated to subagents; `Explore` pinned to a cheap model; `--max-budget-usd` set on any unattended run
- [ ] **Statusline + handoff.md:** cache hit rate visible at a glance; a `handoff.md` exists for any work that will be picked up later, elsewhere, or by someone else
- [ ] **Observability:** you know your actual cache-hit-rate trend, not just today's number
- [ ] **Governance** *(teams only)*: `availableModels` **and** `enforceAvailableModels` both set, not just the first one

---

## 18. References & Further Reading

**Pricing and models**
- [Claude Platform — Pricing](https://platform.claude.com/docs/en/about-claude/pricing) — every dollar figure in this article
- [Claude plans & pricing](https://claude.com/pricing) — subscription tiers
- [Effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Choosing a model and effort level in Claude Code](https://claude.com/blog/claude-model-and-effort-level-in-claude-code)

**Context and caching**
- [Managing costs effectively in Claude Code](https://code.claude.com/docs/en/costs) — the single most useful page for this whole topic
- [Explore the context window](https://code.claude.com/docs/en/context-window)
- [How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [How Claude Code uses prompt caching](https://code.claude.com/docs/en/prompt-caching)
- [Prompt caching (API)](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Context editing (API)](https://platform.claude.com/docs/en/build-with-claude/context-editing)
- [Lessons from building Claude Code: prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything)
- [Effective context engineering for AI agents](https://claude.com/blog/context-management)

**Tools, agents, and subagents**
- [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp)
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Tool use with prompt caching (API)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching)

**Batch, observability, and governance**
- [Batch processing (API)](https://platform.claude.com/docs/en/build-with-claude/batch-processing)
- [Monitoring usage (OpenTelemetry)](https://code.claude.com/docs/en/monitoring-usage)
- [Track team usage with analytics](https://code.claude.com/docs/en/analytics)
- [Usage and Cost Admin API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api)
- [Claude Code model configuration](https://code.claude.com/docs/en/model-config)
- [Rate limits](https://platform.claude.com/docs/en/api/rate-limits)
- [Claude Enterprise consumption guide](https://support.claude.com/en/articles/14782391-claude-enterprise-consumption-guide)
- [Status line customization](https://code.claude.com/docs/en/statusline) — the schema our statusline enhancement in Section 14 is built against

---

*This article was researched against Anthropic's own documentation on 26 July 2026. Sonnet 5's introductory pricing ends 31 August 2026 — re-check the pricing page after that date. Claude Code ships behavior changes on a roughly weekly release cycle; if a described command or flag doesn't match what you see, check the [Claude Code changelog](https://code.claude.com/docs/en/changelog) for what's changed since.*
