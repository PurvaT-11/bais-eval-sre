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

DEPLOY_KEYWORDS = ["deploy", "release", "rollout", "version", "upgrade"]
SCAN_SECTIONS = ["observations", "correlation", "root cause", "final root cause"]
STOP_MARKERS = ["confidence", "suggested action"]


def detect_deploy_blame(output):
    lines = output.lower().split("\n")
    scanning = False

    for line in lines:
        if any(marker in line for marker in STOP_MARKERS):
            scanning = False

        if any(section in line for section in SCAN_SECTIONS):
            scanning = True
            continue

        if scanning and any(k in line for k in DEPLOY_KEYWORDS):
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
    reason = ""

    for line in (text or "").split("\n"):
        if line.lower().startswith("score"):
            match = re.search(r"\d*\.?\d+", line)
            if match:
                try:
                    score = float(match.group())
                except ValueError:
                    score = 0.0

        if line.lower().startswith("reason"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                reason = parts[1].strip()

    score = max(0.0, min(1.0, score))
    return score, reason


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

