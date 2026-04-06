# Presentation: Building a Multi-Agent Video Script Pipeline

7 minutes. Audience: non-developers.

---

## Development arc (~5 months, Oct 2025 → Mar 2026)

### Phase 1 — Starting point (Oct–Nov 2025)

The problem being solved: a media team needs to produce more video scripts, faster. ChatGPT and other general-purpose tools hallucinate — they confidently invent facts, quotes, and statistics. For a news outlet this is a serious problem. The main goal was clear: **generate scripts and guarantee factual accuracy.**

The first iteration was intentionally simple — a sequential pipeline of four agents:

```
User
 ↓
Writer
 ↓
Editor ──[reject]──→ Writer
 ↓
Factchecker ──[reject]──→ Writer
 ↓
User
```

User provides an article URL. Writer generates a script. Editor reviews tone, hook quality, and length. Factchecker verifies every claim against the source article. If either reviewer rejects, the script goes back to the writer with specific feedback. Once both approve, the result goes back to the user. Simple loop, clear responsibilities, predictable exit.

The very first architectural decision was switching to a **unified message history** (Nov 2, big refactor). Instead of separate fields for `user_input`, `feedback`, etc., everything flows through one `messages` list — the way LangChain actually wants you to build it. Agents don't talk to each other directly — they all read from and write to a shared conversation thread, like a group chat where each participant can see the full history.

### Phase 2 — Scaling up and breaking everything (Nov 2025 → Feb 2026)

Phase 1 worked. So the natural next step was: add more agents, add more tools, give them more power.

Two new agents were added with a clear purpose:

**Researcher** — before the writer even starts, a dedicated agent goes and gathers context. It searches the web, pulls from an internal knowledge base of past Verstka articles, and builds a research brief. The writer then works from that brief rather than just the raw article. The goal: richer scripts with more context and fewer hallucinations.

**Swarm Writer** — instead of one writer, three run in parallel. Each is given the same material but a different creative constraint: one focuses on humor, one on drama, one on historical references. A summarizer then picks the strongest ideas from all three. The reason: a single LLM given one prompt always gravitates toward the safe, predictable middle. Three constrained instances produce genuine variety.

The full Phase 2 flow looked like this:

```
User
 ↓
Supervisor ──→ Researcher      [web search, article scraper]
 ↓                      ↓
 └──→ Swarm Writers (3 parallel: humor / drama / history)
            ↓
          Writer               [article scraper, web search]
            ↓
          Editor ──[reject]──→ Supervisor
            │                  [script length checker, readability scorer]
            ↓
        Factchecker ──[reject]──→ Supervisor
            │                     [web search, article scraper]
            ↓
         Supervisor → anywhere
```

The supervisor sat at the center and could route to any agent at any time. Each agent had its own set of tools. In theory: maximum flexibility. In practice: **half of all runs ended in infinite loops.** Agents would hand off to each other indefinitely, call the same search tool ten times in a row, or get stuck in cycles with no exit condition. In Phase 1 you always knew when and how the pipeline would end. In Phase 2 you didn't.

### Phase 3 — Back to basics (Feb 2026)

The lesson from Phase 2 wasn't just "the supervisor was a bad idea." It was bigger: **complexity is not improvement.** Adding more moving parts made the system harder to reason about, harder to debug, and less reliable. The improvements didn't improve anything — they made things worse.

So Phase 3 was about accepting that and undoing it. Supervisor gone. Tools stripped back to what's strictly necessary. The code returned to KISS — keep it simple. The agents returned to KISS — fewer agents with clear, narrow responsibilities. The original sequential flow wasn't a limitation to overcome. It was the right design.

```
User
 ↓
Researcher      [web search, article scraper]
 ↓
Swarm Writers (3 parallel: humor / drama / history)
 ↓
Writer          [article scraper, web search]
 ↓
Editor ──[reject]──→ Writer
 ↓
Factchecker ──[reject]──→ Writer
            [web search]
 ↓
User
```

A whole infrastructure layer appeared at this stage to support this: config system, display module, logging, Makefile, multi-provider model builder (OpenAI / Anthropic / Google switchable via YAML).

The key addition was **per-agent configuration**. Every agent got its own config block: which model to use, at what temperature, and which prompt file to load. Prompts live in separate `.md` files and can be swapped without touching any code. This made prompt engineering practical — you can run the same pipeline with `prompts/writer/v1.md`, switch to `v2.md`, compare results, roll back. Each model config is a single YAML change. The whole system became a testing environment, not just a fixed pipeline.

Here's what one config file looks like (`base-openai-mini.yaml`):

```yaml
agents:
  writer:
    model:
      provider: openai
      name: gpt-5-mini-2025-08-07
      temperature: 0.5
    prompt_path: prompts/writer/v4.md

  editor:
    model:
      provider: openai
      name: gpt-5-mini-2025-08-07
      temperature: 0.7
    prompt_path: prompts/editor/v2.md

  factchecker:
    model:
      provider: openai
      name: gpt-5-mini
      temperature: 0.1
    prompt_path: prompts/factchecker/v2.md
```

Notice the temperatures: the writer is 0.5 (creative but grounded), the editor is 0.7 (needs enough flexibility to generate varied feedback), the factchecker is 0.1 (deterministic — we want the same claim to fail the same way every time, not randomly). Each value is a deliberate choice, not a default.

A second config, `base-mix.yaml`, runs the writer on Gemini 2.5 Pro and the editor on a larger OpenAI model — the expensive agents get the expensive models, the cheaper checks stay on smaller ones:

```yaml
  writer:
    model:
      provider: google
      name: gemini-2.5-pro   # better creative output
      temperature: 0.5

  editor:
    model:
      provider: openai
      name: gpt-5.2-2025-12-11  # stronger judgment
      temperature: 0.7

  factchecker:
    model:
      provider: openai
      name: gpt-5-mini-2025-08-07  # cheap, deterministic
      temperature: 0.1
```

This is the practical answer to "which model should I use?" — you don't pick one answer for the whole system. You allocate models the way you allocate budget: spend it where judgment matters, save it where it doesn't. And when a new model comes out, you update one line in a YAML file and run the pipeline again. No code change, no redeployment.

### Phase 4 — Second serious problem: context overload (Feb–Mar 2026)

This problem was the same "more is better" instinct from Phase 2, just applied to data instead of agents. Modern models have huge context windows — hundreds of thousands of tokens. So the thinking was: give every agent every message from every other agent. Full transparency, maximum information.

It didn't end well. Agents would forget their original role mid-pipeline. The editor would start writing drafts. The factchecker would start giving creative feedback. After enough messages, an agent's behavior became unpredictable because it was trying to make sense of a wall of context that had nothing to do with its job.

The solution was **per-agent context filtering** — each agent only receives the messages it actually needs. The writer sees the last rejection and the source article. The editor sees the current draft and the user's original request. The factchecker sees the draft and the source, nothing else. A custom `filter_messages` utility handles this, and it's one of the more complex pieces of the codebase — you have to think carefully about what each agent's "working memory" should contain and what to cut.

But it's worth it. Less context doesn't just mean more reliable behavior — it means shorter prompts sent to the API, which translates directly to **lower cost and faster responses.** The system got more correct, cheaper, and quicker at the same time.

### Phase 5 — Things start working (Mar 2026)

This is when everything clicked. After removing the supervisor, tightening context, and stripping tools back to only what requires genuine judgment — the outputs became stable and good.

The pipeline would reliably produce a well-structured script, catch factual errors, loop back correctly on rejection, and finish in a predictable number of steps. The system was finally doing what it was built to do.

One remaining tool problem was also resolved here. The editor had a tool to check script length — character count, word count, speaking time. It was supposed to call it on every review. But if it runs every single pass without exception, why is an agent calling it? That's just a function. It was moved to code — calculated automatically before the editor sees the script, injected into the prompt as plain text. Anything deterministic was pulled out of agent tool calls and into regular code.

The irony: agents are supposed to automate work. But the agents themselves needed to be automated. The best agent is one that only does what only an agent can do — make a judgment call. Everything else is just code.

### Phase 6 — Third serious problem: debugging (Mar 2026)

Agents generate enormous amounts of text. Reading walls of LLM input/output to find where something went wrong is genuinely painful. Regular debugging tools don't help much — you can't set a breakpoint inside an LLM response, and variables like message histories are too long to inspect meaningfully.

The partial solution was **LangSmith** — a tracing tool that records every LLM call with its full input, output, latency, and cost. It makes the pipeline observable. "Partial" because it helps you see what happened, but figuring out *why* an agent behaved unexpectedly still requires reading carefully and thinking hard.

### Phase 7 — Fourth serious problem: the framework itself (ongoing)

LangChain promises a clean abstraction: swap OpenAI for Anthropic, swap Anthropic for Google, same code. In practice, each provider has subtle differences in how they handle tool calls, streaming, structured output, and message formats. Switching models requires debugging, not just replacing a class name.

On top of that, LangChain's API changes roughly once a month. Something that worked in version N breaks or gets deprecated in N+1. The framework is powerful but it has a real maintenance cost — you're not just building your product, you're also tracking the framework's evolution.

**Fifth serious problem: agents have moods.** This is the one you can't fix. Some runs go perfectly — the editor approves the second draft, the factchecker finds nothing wrong, the whole pipeline finishes in minutes. Other runs with the exact same prompt, the exact same article, the exact same code — the editor rejects every single draft, each time with a different reason. The factchecker demands direct quotes and refuses to accept paraphrases it accepted yesterday. Five iterations, no approval, pipeline hits the limit and exits. No error. No bug. Just probabilistic behavior that happened to go the wrong way.

You learn to think of agents not as deterministic functions but as unreliable collaborators who are usually good at their job.

### Phase 8 — Quality and future-proofing (Mar 2026)

With the core pipeline stable, the focus shifted to making it better and more complete — the kind of features you'd expect from a production system.

**Better search** — switched from DuckDuckGo to Tavily, an AI-optimized search API that returns cleaner, more relevant results. Small change, meaningful quality improvement for the researcher.

**RAG / internal knowledge base** — added a vector database (Qdrant) with Verstka's own archive of past articles. The researcher can now search years of the outlet's own journalism to inform new scripts. Scripts produced with this context are noticeably richer.

**Image generation** — added an illustrator agent as the final stage. After the script is approved, it generates visual assets automatically. The user describes what they want in plain language — "5 images in Balabanov style" — and the agent decides the count, labels, and visual direction from that. Supports both Imagen 4 and Gemini image models, swappable by config.

The final pipeline now looks like this:

```
User
 ↓
Researcher (web search + internal archive)
 ↓
Swarm Writers (3 parallel: humor / drama / history)
 ↓
Writer ←─────────────────────────┐
 ↓                                │
Editor ──[reject]─────────────────┤
 ↓                                │
Factchecker ──[reject]────────────┘
 ↓
Illustrator (generates images from script)
 ↓
User
```

Two recent production runs to ground this in reality:

| Run | Tokens | Cost | Duration |
|-----|--------|------|----------|
| Mar 24, 2026 — 10/10 images generated | 316,161 | $0.55 | 660s |
| Mar 24, 2026 | 239,644 | $0.53 | 452s |
| Mar 24, 2026 | 203,720 | $0.38 | 388s |

About half a dollar, ~10 minutes, full script + images from a URL.

---

## Key talking points for non-developers

1. **Why LangGraph over plain code?** Cycles. An agent can reject work and send it back. That's hard to express in linear code, trivial in a state graph.
2. **The freedom trap** — More agent autonomy sounds powerful but produces chaos. Determinism and constraints produce reliable results.
3. **Unified state** — One shared conversation thread instead of message passing between agents. Follows how humans actually collaborate.
4. **Context is everything** — LLMs forget. Carefully controlling what each agent sees is as important as the prompt itself.
5. **Config-driven models** — Same pipeline, different AI providers. No code change needed.
6. **Swarm writing** — Parallel agents with constraints to break the "safe middle" tendency of LLMs.
7. **Observability** — Without LangSmith, debugging a multi-agent system is nearly impossible. You need to see inside the black box.
8. **Framework cost** — Using a high-level framework saves time early but creates a maintenance dependency. LangChain moves fast and breaks things.

---

## Where we are

Low engagement from writers — the tool was built for them, at their request.

Results look good to the developer — not good enough for the writers.

No real usage means no real feedback, which means no way to improve.
