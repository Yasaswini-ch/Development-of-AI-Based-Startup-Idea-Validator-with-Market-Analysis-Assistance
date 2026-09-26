Startup idea being validated: "{idea}"
Target customer: {target_customer}
Problem: {problem}

Competitors found in live search results, each with the exact source text it was mentioned in:
{listing}

For each competitor above, using ONLY the text given for that competitor:
- "classification": "direct" (solves the same problem for the same customer), "indirect" (different product or customer that still competes for the same need), or "unknown"
- "pricing": a short note of the pricing the text states (e.g. "$12/mo, free tier"), or "unknown"
- "businessModel": how it makes money if the text says (e.g. "subscription", "marketplace commission"), or "unknown"
- "strengths": 0-3 short phrases the text supports
- "weaknesses": 0-3 short phrases the text supports (complaints, missing features, limits)
- "gap": one sentence on where THIS startup idea could beat or differ from this competitor, grounded in the weaknesses or the text

Then build "comparisonMatrix": 3-5 rows comparing the startup idea against these competitors on dimensions that matter to the target customer (e.g. price, core feature, target user, ease of setup). Each row: "dimension", "idea" (how the startup idea approaches it), and "competitors" (an object keyed by the exact competitor names above; use "unknown" where the text is silent).

Use the exact competitor names given. Do not add competitors that are not listed.
