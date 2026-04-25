import json
from agent import run_agent
from evaluator import detect_deploy_blame, extract_confidence, score_reasoning

with open("incidents.json") as f:
    incidents = json.load(f)

def run_experiment(version):
    results = []

    print(f"\n===== {version.upper()} PROMPT =====\n")

    for inc in incidents:
        output = run_agent(inc, version)

        blamed = detect_deploy_blame(output)
        confidence = extract_confidence(output)
        score, reason = score_reasoning(output, inc["expected_root_cause"])

        correct = (blamed == inc["is_deploy_cause"])

        print(f"\n--- {inc['id']} ---")
        print(f"Blamed Deploy: {blamed}")
        print(f"Correct: {correct}")
        print(f"Confidence: {confidence}")
        print(f"Score: {score}")

        results.append({
            "is_deploy": inc["is_deploy_cause"],
            "blamed": blamed,
            "correct": correct,
            "confidence": confidence,
            "score": score
        })

    return results


def summarize(results):
    total = len(results)
    non_deploy = [r for r in results if not r["is_deploy"]]
    false_attr = [r for r in non_deploy if r["blamed"]]
    correct = [r for r in results if r["correct"]]

    far = len(false_attr)/len(non_deploy)
    acc = len(correct)/total

    print("\nSUMMARY")
    print("False Attribution Rate:", far)
    print("Accuracy:", acc)

    return far


naive = run_experiment("naive")
grounded = run_experiment("grounded")

far1 = summarize(naive)
far2 = summarize(grounded)

print("\nBias Reduction:", far1 - far2)

print("\nHIGH CONFIDENCE WRONG CASES:\n")

for inc, res in zip(incidents, naive):
    if not res["correct"] and res["confidence"] >= 0.7:
        print(f"\nCase {inc['id']}")
        print("Expected:", inc["expected_root_cause"])
        print("Agent Output:", res["confidence"])