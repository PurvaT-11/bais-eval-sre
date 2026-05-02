import json
import sys

def load_data():
    with open("incidents.json") as f:
        incidents = {inc["id"]: inc for inc in json.load(f)}

    with open("results.json") as f:
        results_list = json.load(f)
        results = {r["id"]: r for r in results_list}

    return incidents, results


def inspect_case(case_id):
    incidents, results = load_data()

    if case_id not in incidents:
        print(f"Case {case_id} not found.")
        return

    inc = incidents[case_id]
    res = results.get(case_id, {})

    print("\n" + "="*60)
    print(f"CASE: {case_id}")
    print("="*60)

    print(f"\nIncident:\n{inc['incident']}")
    print(f"\nDistractor Type: {inc.get('distractor_type', 'N/A')}")
    print(f"Expected Root Cause:\n{inc['expected_root_cause']}")

    print("\n--- Agent Behavior ---")
    print(f"Blamed Deploy: {res.get('blamed')}")
    print(f"Confidence: {res.get('confidence')}")

    print("\n--- Evaluation ---")
    print(f"OpenAI Score: {res.get('score_openai')}")
    print(f"Ollama Score: {res.get('score_ollama')}")
    print(f"Disagreement: {res.get('disagree')}")

    print("\n--- Insight ---")
    if not inc["is_deploy_cause"] and res.get("blamed"):
        print("⚠️ Model ignored actual cause and defaulted to deployment (recency anchoring).")
    elif inc["is_deploy_cause"] and not res.get("blamed"):
        print("⚠️ Model failed to identify deployment as actual cause.")
    else:
        print("✓ Model reasoning aligned with expected cause.")

    print("="*60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect.py <case_id>")
    else:
        inspect_case(sys.argv[1])