import re
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEPLOY_KEYWORDS = ["deploy", "release", "rollout", "version", "upgrade"]

def detect_deploy_blame(output):
    lines = output.lower().split("\n")
    in_root = False

    for line in lines:
        if "likely root cause" in line:
            in_root = True
            continue
        if in_root:
            if line.strip() == "" or "confidence" in line:
                break
            if any(k in line for k in DEPLOY_KEYWORDS):
                return True

    return False


def extract_confidence(output):
    lines = output.split("\n")

    for i, line in enumerate(lines):
        if "confidence" in line.lower():
            # Check next line (since number is often on next line)
            if i + 1 < len(lines):
                match = re.search(r"\d*\.?\d+", lines[i + 1])
                if match:
                    return float(match.group())

            # fallback: same line
            match = re.search(r"\d*\.?\d+", line)
            if match:
                return float(match.group())

    return 0.0


def score_reasoning(output, expected):
    prompt = f"""
Evaluate this AI SRE output.

Expected Root Cause:
{expected}

Agent Output:
{output}

Score from 0.0 to 1.0 based on correctness and reasoning quality.

Return STRICTLY in this format:
Score: <number between 0 and 1>
Reason: <one short sentence>
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    text = response.choices[0].message.content.strip()

    score = 0.0
    reason = "Parsing failed"

    for line in text.split("\n"):
        if line.lower().startswith("score"):
            try:
                num = re.search(r"\d*\.?\d+", line)
                if num:
                    score = float(num.group())
            except:
                score = 0.0

        if line.lower().startswith("reason"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                reason = parts[1].strip()

    return score, reason