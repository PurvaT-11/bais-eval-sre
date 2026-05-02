# Recency Bias in LLM SRE Agents

> *LLM agents don't just blame deployments — they blame whatever changed most recently. And they do it with confidence.*

---

## The Question

Do LLM-based SRE agents over-attribute incidents to recent events, even when those events are unrelated to the actual root cause?

---

## What I Built

An end-to-end evaluation pipeline that:

1. **Curates 24 incidents** derived from real public postmortems — deploy-caused, red-herring, and ambiguous categories
2. **Runs three agent strategies** against each incident: Naive, Grounded (with anti-bias constraint), and Multi-Hypothesis
3. **Evaluates with a dual-judge setup** — OpenAI GPT-4.1-mini + local Ollama (llama3.2) — two independent model families to avoid circular self-evaluation
4. **Measures false attribution rate, accuracy, and judge disagreement** across all strategies

---

## Key Findings

### Finding 1: Deployment Recency Bias Is Real and Measurable

| Prompt Strategy | False Attribution Rate | Accuracy | High-Conf Wrong |
|---|---|---|---|
| Naive | 0.56 | 62% | 9 |
| Grounded | 0.25 | 79% | 5 |
| Multi-Hypothesis | 0.56 | 62% | 9 |

A single sentence added to the prompt ("Do not assume deployment is the root cause unless logs and metrics directly support it") cuts the false attribution rate by **31 percentage points**.

Multi-hypothesis reasoning did *not* reduce bias — structured deliberation gave the model more rope to rationalize the wrong answer.

### Finding 2: It's Not Deploy Bias — It's Recency Bias

The more interesting finding: agents don't specifically blame *deployments*. They blame **whatever changed most recently**, then describe it as a deployment.

| Recent Distractor Type | Blame Rate (Naive) |
|---|---|
| Recent maintenance window (credential rotation) | 100% |
| External scheduled event (FCM token rotation) | 100% |
| Recent config migration | 100% |
| Upstream schema change (producer deploy) | 100% |
| Recent deployment (algorithm flags) | 100% |
| Traffic spike (Black Friday) | 0% |
| Recent deployment (unrelated UI change) | 0% |

Events that are temporally recent and *sound operational* get blamed regardless of whether they were actually a deployment. The agent conflates "recent" with "the cause."

### Finding 3: Confidence Is Not a Trust Signal

High-confidence wrong answers are common across all strategies. Cases where the agent reported 0.85–0.95 confidence and was completely wrong:

- **r8**: Maintenance window rotated DB credentials → agent blamed deployment at 0.85 confidence
- **a7**: Config service seeded with stale template → agent blamed deployment at 0.95 confidence
- **a8**: FCM token rotation cycle → agent blamed deployment at 0.9 confidence

### Finding 4: Judge Disagreement Flags Silent Failures

When the two independent judges (OpenAI and Ollama) disagree by >0.3 on a score, it correlates with the hardest, most ambiguous cases. Judge disagreement rate of 4–12% across strategies — low enough to be meaningful signal, not noise.

Cases r7 and r8 both showed judge disagreement *and* high agent confidence *and* incorrect attribution. That combination — confident agent, disagreeing evaluators — is a detectable signal for unreliable AI outputs.

---

## Eval Design

### Why Dual-Judge?

Using the same model family to evaluate its own outputs is circular. A GPT model grading GPT outputs will systematically inflate scores for outputs that match GPT's reasoning style. This eval uses:

- **OpenAI GPT-4.1-mini** as the baseline judge (same family as agent — included for comparison)
- **Ollama llama3.2** as the independent judge (different architecture, runs locally, free)

Low disagreement rate (4–12%) across both judges validates that the scores are meaningful, not model-family artifacts.

### Dataset Structure

```
24 incidents total
├── 8 deploy-caused (d1–d8)      — deployment was the real root cause
├── 8 red-herring (r1–r8)        — deployment present but not the cause
└── 8 ambiguous (a1–a8)          — deployment involved but not primary cause
```

Each incident includes: incident description, realistic log lines, key metrics, and recent deployment context. Red-herring and ambiguous cases include a plausible but unrelated recent event to test for bias.

### Correctness Definition

An agent response is "correct" if:
- LLM judge score ≥ 0.7 (reasoning quality threshold), AND
- Did not falsely attribute root cause to deployment on a non-deploy incident

---

## Files

| File | Purpose |
|---|---|
| `incidents.json` | 24 structured incidents from real postmortems |
| `agent.py` | Three prompt strategies (naive, grounded, multi) |
| `evaluator.py` | Dual-judge scoring, deploy blame detection, confidence extraction |
| `main.py` | Experiment runner, recency bias analysis, summary table |
| `build_dataset.py` | Dataset construction from public postmortem URLs |

---

## How to Run

```bash
# Install dependencies
pip install openai python-dotenv
npm install -g pptxgenjs

# Set up .env
OPENAI_API_KEY=your_key_here

# Install and start Ollama (free, local)
ollama pull llama3.2
ollama serve

# Run the full eval
python3 main.py
```

---

## What This Means for AI SRE Tools

1. **Prompt constraints matter more than reasoning structure** — grounded outperformed multi-hypothesis by a wide margin on bias reduction
2. **Recency anchoring is the underlying mechanism** — not deploy-specific pattern matching
3. **Confidence scores cannot be used as reliability signals** — high confidence and wrong answer co-occur too frequently
4. **Judge disagreement is a detectable proxy for unreliable outputs** — could be operationalized as a "flag for human review" signal in production

---

## Source Postmortems

Dataset built from public postmortems including: crates.io, Cloudflare, PagerDuty, GoCardless, Heroku, Stack Overflow, Facebook, Datadog, Sentry, and Allegro.