# Recency Bias in LLM SRE Agents

> LLM agents don’t just blame deployments — they anchor to whatever changed most recently, and often get it wrong with high confidence.

---

## Problem

During incident analysis, LLM-based SRE agents frequently attribute failures to recent deployments.

The question is:

**Is this actually deployment bias, or something more general?**

---

## What This Project Does

This project builds a small evaluation pipeline to test how LLM agents reason about incidents.

It:
- Uses **24 incidents derived from real postmortems**
- Runs **three prompt strategies**:
  - Naive
  - Grounded (anti-bias constraint)
  - Multi-hypothesis
- Evaluates outputs using **two independent judges**:
  - OpenAI (same family as the agent)
  - Local Ollama model (different architecture)
- Measures:
  - False Attribution Rate (FAR)
  - Accuracy
  - High-confidence wrong cases
  - Judge disagreement

---

## Key Findings

### 1. Deployment Bias Exists — But It's Not the Real Problem

| Strategy | FAR | Accuracy |
|----------|-----|----------|
| Naive    | 0.56 | 0.62 |
| Grounded | 0.25 | 0.79 |
| Multi    | 0.56 | 0.62 |

A simple prompt constraint reduces false attribution significantly.  
But the deeper issue remains.

---

### 2. The Real Failure Mode: Recency Anchoring

The model does not specifically detect deployments.

Instead, it:
- looks for **what changed recently**
- assumes that change caused the issue
- expresses it as a deployment-related explanation

Examples of misattributed causes:
- maintenance windows
- config migrations
- external token rotations
- upstream changes

**The model is anchoring on recency, not reasoning about causality.**

---

### 3. Confidence Is Misleading

Wrong answers are often high confidence (0.85–0.95).

Example:
- Maintenance window rotated DB credentials  
- Model blamed deployment  
- Confidence: 0.85  

Confidence does not reliably track correctness.

---

### 4. Some Failures Are Hard to Detect

In several cases:
- the agent is wrong  
- confidence is high  
- evaluators disagree  

Example (r8):

- OpenAI score: 0.4  
- Ollama score: 0.85  
- Agent confidence: 0.85  

**Even evaluation systems cannot reliably flag the error.**

---

## Evaluation Design

### Dual Judge Setup

Using the same model to evaluate itself is circular.

This setup uses:
- OpenAI → baseline judge  
- Ollama → independent judge  

Disagreement between them is treated as a signal.

---

### Dataset

24 incidents:
-8 deploy-caused
-8 red-herring (deploy present but irrelevant)
-8 ambiguous

Each includes:
- incident description  
- logs  
- metrics  
- recent changes  

---

### Correctness Definition

A response is considered correct if:
- judge score ≥ 0.7  
- AND no false deployment attribution on non-deploy incidents  

---

## Repo Structure
-agent.py # prompt strategies
-evaluator.py # scoring + deploy detection + judges
-main.py # runs experiments + summary
-inspect_case.py # deep-dive on individual failures
-incidents.json # dataset


---

## Running the Project

```bash
pip install openai python-dotenv

# Set API key
OPENAI_API_KEY=your_key_here

# Optional: local judge
ollama pull llama3.2
ollama serve

python main.py
```
---
##Takeaways
-LLM SRE agents anchor on recency, not causality
-Prompting reduces bias, but does not remove it
-Confidence is not a reliable signal
-Judge disagreement can help identify unreliable outputs
---
##Why This Matters

In real incidents, this behavior can:

1. mislead engineers toward the wrong root cause
2. increase time to resolution
3. reduce trust in AI-assisted debugging
--- 
##Sources

Incidents adapted from public postmortems including:
Cloudflare, Datadog, PagerDuty, GoCardless, Heroku, Facebook, Stack Overflow, and others.
