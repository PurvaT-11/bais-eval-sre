from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

NAIVE_PROMPT = """You are an expert SRE assistant investigating an incident.

Incident: {incident}

Logs:
{logs}

Metrics:
{metrics}

Deployments:
{deployments}

Analyze and respond STRICTLY in this format (no extra text):

Observations:
- <bullet>

Correlation:
- <bullet>

Likely Root Cause:
<single sentence>

Confidence (0.0-1.0):
<number only>

Suggested Action:
- <bullet>
"""

GROUNDED_PROMPT = """You are an expert SRE assistant investigating an incident.

Incident: {incident}

Logs:
{logs}

Metrics:
{metrics}

Deployments:
{deployments}

Important: Do not assume deployment is the root cause unless logs and metrics directly support it. 
Consider infrastructure, external systems, traffic, and capacity equally.

Analyze and respond STRICTLY in this format (no extra text):

Observations:
- <bullet>

Correlation:
- <bullet>

Likely Root Cause:
<single sentence>

Confidence (0.0-1.0):
<number only>

Suggested Action:
- <bullet>


"""

MULTI_PROMPT = """You are an expert SRE.

Incident:
{incident}

Logs:
{logs}

Metrics:
{metrics}

Deployments:
{deployments}

Step 1: List the top 2 possible root causes.
Step 2: For each, explain supporting evidence and why it might be wrong.
Step 3: Choose the most likely root cause.

Return format:

Hypothesis 1:
<text>

Hypothesis 2:
<text>

Final Root Cause:
<text>

Confidence (0.0-1.0):
<number>
"""

def run_agent(incident, prompt_version="naive"):
    if prompt_version == "naive":
        prompt_template = NAIVE_PROMPT
    elif prompt_version == "grounded":
        prompt_template = GROUNDED_PROMPT
    elif prompt_version == "multi":
        prompt_template = MULTI_PROMPT
    else:
        raise ValueError("Unknown prompt version")

    prompt = prompt_template.format(
        incident=incident["incident"],
        logs=incident["logs"],
        metrics=incident["metrics"],
        deployments=incident["deployments"]
    )

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content