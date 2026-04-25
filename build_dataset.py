from openai import OpenAI
import os
import time
import requests
import json
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

POSTMORTEM_SOURCES = [
    # DEPLOY-CAUSED (5)
    (
        "https://blog.rust-lang.org/inside-rust/2023/07/21/crates-io-postmortem.html",
        "deploy", True,
        "crates.io download breakage from deployment bug in URL generation"
    ),
    (
        "https://blog.rust-lang.org/inside-rust/2023/02/08/dns-outage-portmortem.html",
        "deploy", True,
        "DNS resolution failure during crates.io infrastructure deployment"
    ),
    (
        "https://status.pagerduty.com/incidents/vbp7ht2647l8",
        "deploy", True,
        "PagerDuty container orchestration DNS failure from config deployment"
    ),
    (
        "https://gocardless.com/blog/incident-review-api-and-dashboard-outage-on-10th-october/",
        "deploy", True,
        "GoCardless API/Dashboard outage from bad config combined with failures"
    ),
    (
        "https://blog.heroku.com/how-i-broke-git-push-heroku-main",
        "deploy", True,
        "Heroku git push broken by incorrect deployment process"
    ),
    # NON-DEPLOY: Config/Infrastructure (3)
    (
        "https://web.archive.org/web/20201020103424/https://stackstatus.net/post/96025967369/outage-post-mortem-august-25th-2014",
        "config", False,
        "Stack Overflow outage from bad firewall configuration"
    ),
    (
        "https://engineering.fb.com/2021/10/05/networking-traffic/outage-details/",
        "config", False,
        "Facebook global outage from backbone router configuration changes"
    ),
    (
        "https://www.datadoghq.com/blog/2020-09-25-infrastructure-connectivity-issue/",
        "config", False,
        "Datadog outage from bad service discovery config propagation"
    ),
    # NON-DEPLOY: External dependency (3)
    (
        "https://blog.sentry.io/2016/06/14/security-incident-june-12-2016",
        "external", False,
        "Sentry data leak from wrong Amazon S3 settings"
    ),
    (
        "https://allegro.tech/2018/08/postmortem-why-allegro-went-down.html",
        "external", False,
        "Allegro e-commerce outage from traffic spike hitting config resource limits"
    ),
    # AMBIGUOUS (2) — agent sees deploy but real cause is something else
    (
        "https://blog.cloudflare.com/1-1-1-1-lookup-failures-on-october-4th-2023/",
        "ambiguous", False,
        "Cloudflare DNS resolution failures — internal software error, not a recent deployment"
    ),
    (
        "https://web.archive.org/web/20211016040522/https://blog.cloudflare.com/cloudflare-outage-on-july-17-2020/",
        "ambiguous", False,
        "Cloudflare outage from network config typo during maintenance, not standard deployment"
    ),
]

EXTRACT_PROMPT = """You are extracting structured SRE incident data from a public postmortem article.

Article text:
{text}

Known root cause summary (use this to set expected_root_cause accurately):
{known_cause}

Extract and return ONLY valid JSON in this exact schema, nothing else:
{{
  "id": "{id}",
  "incident": "<1-2 sentence description of what went wrong, as an alert would describe it>",
  "logs": "<2-4 realistic log lines that would have been visible during the incident, formatted as [TIME] LEVEL: message>",
  "metrics": "<key metrics that changed during the incident, e.g. error rates, latency, CPU>",
  "deployments": "<any recent deployment mentioned, or 'No recent deployment noted' if none>",
  "is_deploy_cause": {is_deploy_cause},
  "expected_root_cause": "<1 sentence precise root cause from the postmortem>",
  "source": "{url}",
  "category": "{category}"
}}

Rules:
- Keep incident description neutral — don't reveal the cause
- Make logs realistic but brief (2-4 lines max)
- If no deployment is mentioned in the article, add a plausible unrelated recent deployment to test for bias
- expected_root_cause must match the known_cause provided
"""


def fetch_article(url: str) -> str:
    """Fetch and return plain text from a URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (research project)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        # Simple HTML stripping — good enough for postmortems
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self._skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "nav", "header", "footer"):
                    self._skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "nav", "header", "footer"):
                    self._skip = False

            def handle_data(self, data):
                if not self._skip and data.strip():
                    self.text_parts.append(data.strip())

        parser = TextExtractor()
        parser.feed(resp.text)
        text = " ".join(parser.text_parts)
        # Trim to ~3000 chars to stay within context
        return text[:3000]
    except Exception as e:
        print(f"  ⚠ Fetch failed: {e}")
        return ""


def extract_incident(url, category, is_deploy_cause, known_cause, idx):
    """Use LLM to extract structured incident data from article."""
    print(f"  Fetching: {url[:60]}...")
    text = fetch_article(url)

    if not text:
        print(f"  ⚠ Skipping (fetch failed)")
        return None

    prompt = EXTRACT_PROMPT.format(
        text=text,
        known_cause=known_cause,
        id=f"{'d' if is_deploy_cause else 'r'}{idx}",
        is_deploy_cause=str(is_deploy_cause).lower(),
        url=url,
        category=category,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()

        # Clean markdown formatting safely
        if raw.startswith("```"):
            parts = raw.split("```")
            if len(parts) >= 2:
                raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:].strip()

        incident = json.loads(raw)
        print(f"  ✓ Extracted: {incident['id']} — {incident['incident'][:60]}...")
        return incident
    except Exception as e:
        print(f"  ✗ Extraction failed: {e}")
        return None


def main():
    print("=" * 60)
    print("Building incidents.json from real postmortems")
    print("=" * 60)

    incidents = []
    deploy_idx = 1
    redherring_idx = 1

    for url, category, is_deploy_cause, known_cause in POSTMORTEM_SOURCES:
        idx = deploy_idx if is_deploy_cause else redherring_idx
        print(f"\n[{category.upper()}] {'deploy-cause' if is_deploy_cause else 'red-herring'}")

        incident = extract_incident(url, category, is_deploy_cause, known_cause, idx)
        if incident:
            incidents.append(incident)
            if is_deploy_cause:
                deploy_idx += 1
            else:
                redherring_idx += 1

        time.sleep(1)  # be polite to servers

    # Save
    with open("incidents.json", "w") as f:
        json.dump(incidents, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✓ Built {len(incidents)} incidents from real postmortems")
    deploy_count = sum(1 for i in incidents if i["is_deploy_cause"])
    print(f"  Deploy-caused  : {deploy_count}")
    print(f"  Red-herring    : {len(incidents) - deploy_count}")
    print(f"  Saved to       : incidents.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
