# Deployment Recency Bias in LLM SRE Agents

## Question
Do LLM agents over-attribute incidents to recent deployments?

## Method
- 10 incidents (5 real deploy, 5 red herring)
- Ran agent with naive vs grounded prompts
- Measured false attribution rate

## Finding
LLMs showed bias toward recent deployments.
Prompt constraint reduced this bias significantly.

## Insight
Confidence is not a reliable trust signal.
High-confidence wrong answers are common.