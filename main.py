import json
from agent import run_agent
from evaluator import (
    detect_deploy_blame,
    extract_confidence,
    score_reasoning_openai,
    score_reasoning_ollama,
)

with open("incidents.json") as f:
    incidents = json.load(f)

def run_experiment(version):
    results = []

    print(f"\n===== {version.upper()} PROMPT =====\n")

    for inc in incidents:
        output = run_agent(inc, version)

        blamed = detect_deploy_blame(output)
        confidence = extract_confidence(output)

        score_openai, _ = score_reasoning_openai(output, inc["expected_root_cause"])
        score_ollama, _ = score_reasoning_ollama(output, inc["expected_root_cause"])

        disagree = False
        # Only flag disagreement if ollama actually scored something
        if score_ollama is not None and score_ollama > 0.0:
            disagree = abs(score_openai - score_ollama) > 0.3
        else:
            disagree = None  # inconclusive — ollama didn't parse

        correct = (score_openai >= 0.7) and not (
            inc["is_deploy_cause"] is False and blamed is True
        )

        print(f"\n--- {inc['id']} ---")
        print(f"Blamed Deploy: {blamed}")
        print(f"Correct: {correct}")
        print(f"Confidence: {confidence}")
        print(f"Score (OpenAI): {score_openai}")
        print(f"Score (Ollama): {score_ollama}")
        print(
            f"Disagreement: {'YES' if disagree is True else 'NO' if disagree is False else 'N/A (Ollama parse fail)'}"
        )

        results.append({
            "is_deploy": inc["is_deploy_cause"],
            "blamed": blamed,
            "correct": correct,
            "confidence": confidence,
            "score_openai": score_openai,
            "score_ollama": score_ollama,
            "disagree": disagree,
            "id": inc["id"],
        })

    return results


def summarize(label, results):
    total = len(results)
    non_deploy = [r for r in results if not r["is_deploy"]]
    false_attr = [r for r in non_deploy if r["blamed"]]
    correct = [r for r in results if r["correct"]]
    high_conf_wrong = [r for r in results if (not r["correct"] and r["confidence"] >= 0.8)]
    disagreements = [r for r in results if r["disagree"] is True]
    inconclusive = [r for r in results if r["disagree"] is None]

    far = (len(false_attr) / len(non_deploy)) if non_deploy else 0.0
    acc = (len(correct) / total) if total else 0.0
    disagree_rate = len(disagreements) / max(1, (total - len(inconclusive)))

    print("Judge Disagreement Rate:", disagree_rate)

    return {
        "label": label,
        "FAR": far,
        "Accuracy": acc,
        "HighConfWrong": len(high_conf_wrong),
        "DisagreeRate": disagree_rate,
    }

def print_summary_table(summaries):
    print("\n" + "=" * 78)
    print(f"{'Prompt':<18}{'FAR':>7}{'Accuracy':>12}{'HighConfWrong':>16}{'DisagreeRate':>14}")
    print("-" * 78)
    for s in summaries:
        print(
            f"{s['label']:<18}{s['FAR']:>7.2f}{s['Accuracy']:>12.2f}{s['HighConfWrong']:>16d}{s['DisagreeRate']:>14.2f}"
        )
    print("=" * 78)


naive = run_experiment("naive")
grounded = run_experiment("grounded")
multi = run_experiment("multi")

s_naive = summarize("Naive", naive)
s_grounded = summarize("Grounded", grounded)
s_multi = summarize("Multi", multi)

print_summary_table([s_naive, s_grounded, s_multi])

print(f"\nBias Reduction (Naive → Grounded): {s_naive['FAR'] - s_grounded['FAR']:.2f}")

print("\nHIGH CONFIDENCE WRONG CASES:\n")

for inc in incidents:
    res = next((r for r in naive if r["id"] == inc["id"]), None)
    if res and (not res["correct"] and res["confidence"] >= 0.8):
        print(f"\nCase {inc['id']}")
        print("Expected:", inc["expected_root_cause"])
        print("Confidence:", res["confidence"])
        print("Score (OpenAI):", res["score_openai"])
        print("Score (Ollama):", res["score_ollama"])
        print(
            "Disagreement:",
            "YES"
            if res["disagree"] is True
            else "NO"
            if res["disagree"] is False
            else "N/A (Ollama parse fail)",
        )
        print("Blamed Deploy:", res["blamed"])
