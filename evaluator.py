import os
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Agent/OpenAI judge (baseline, circular)
openai_client = OpenAI()

# Ollama judge (local, independent)
ollama_client = OpenAI(
    api_key="ollama",
    base_url="http://localhost:11434/v1",
)

OPENAI_JUDGE_MODEL = "gpt-4.1-mini"
OLLAMA_JUDGE_MODEL = "llama3"

DEPLOY_KEYWORDS = [
    "deploy",
    "release",
    "rollout",
    "caused by.*version",
    "introduced in",
    "triggered by.*upgrade",
]


def detect_deploy_blame(output):
    """
    Returns True only if the agent attributes root cause to a deployment.
    Scans only the root cause / final root cause section.
    """
    lines = output.lower().split("\n")
    in_root_cause = False

    for line in lines:
        # Enter root cause section
        if "likely root cause" in line or "final root cause" in line:
            in_root_cause = True
            continue

        # Exit at confidence or suggested action
        if in_root_cause and (
            "confidence" in line or "suggested action" in line or "hypothesis" in line
        ):
            break

        # Check for deploy blame in root cause section
        if in_root_cause and line.strip():
            for k in ["deploy", "release", "rollout"]:
                if k in line:
                    return True
            # Check version-caused patterns
            if re.search(r"(v\d+\.\d+|version|upgrade).*(caus|introduc|trigger)", line):
                return True

    return False


def extract_confidence(output):
    lines = output.split("\n")

    for i, line in enumerate(lines):
        if "confidence" in line.lower():
            # Check next line (since number is often on next line)
            if i + 1 < len(lines):
                match = re.search(r"\d+\.\d+|\d+", lines[i + 1])
                if match:
                    return float(match.group())

            # fallback: same line
            match = re.search(r"\d+\.\d+|\d+", line)
            if match:
                return float(match.group())

    return 0.0


def rule_based_score(output, expected):
    output = (output or "").lower()
    expected = (expected or "").lower()
    keywords = [w for w in expected.split() if len(w) > 4]
    matches = sum(1 for w in keywords if w in output)
    return min(1.0, matches / max(2, len(keywords)))


def parse_score(text):
    score = 0.0
    reason = "No reason given"
    lines = (text or "").strip().split("\n")

    for line in lines:
        line_lower = line.lower()
        if "score" in line_lower:
            match = re.search(r"(\d*\.?\d+)", line)
            if match:
                try:
                    score = float(match.group(1))
                except ValueError:
                    pass
        if "reason" in line_lower and ":" in line:
            reason = line.split(":", 1)[1].strip()

    # fallback: if still 0.0, try parsing first number in entire response
    if score == 0.0:
        match = re.search(r"(\d\.\d+|\d+\.?\d*)", text or "")
        if match:
            try:
                score = float(match.group(1))
            except ValueError:
                pass

    return max(0.0, min(1.0, score)), reason


def score_reasoning_openai(output, expected):
    prompt = f"""
Evaluate this AI SRE output.

Expected Root Cause:
{expected}

Agent Output:
{output}

Score from 0.0 to 1.0.

Return:
Score: <number>
Reason: <short>
"""

    response = openai_client.chat.completions.create(
        model=OPENAI_JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    text = response.choices[0].message.content.strip()
    return parse_score(text)


def score_reasoning_ollama(output, expected):
    prompt = f"""You are evaluating an AI incident analysis.

Expected root cause: {expected}

Agent output: {output}

Reply with ONLY two lines, exactly like this example:
Score: 0.8
Reason: Correctly identified the database failure

Now evaluate:"""

    try:
        response = ollama_client.chat.completions.create(
            model=OLLAMA_JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        text = response.choices[0].message.content.strip()
        print("[JUDGE: OLLAMA]")
        return parse_score(text)
    except Exception as e:
        print("[OLLAMA FAILED]", e)
        return None, "Ollama failed"
