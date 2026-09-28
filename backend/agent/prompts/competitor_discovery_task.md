Startup idea being validated: "{idea}"
Target customer: {target_customer}
Problem: {problem}

Live search results about competitors and existing solutions, each with an id:
{listing}

Names an automatic entity tagger picked out of these results (may be incomplete, and may include publishers, platforms or other non-competitors): {ner_hints}

Step 1 - find competitors. List up to {max_competitors} companies or products from the results above that a customer could use instead of this startup idea to solve the same need. Rules:
- Only include a name that is written in the text of at least one result above, spelled exactly as it appears there.
- Do not include publishers, review sites, news outlets, app stores, operating systems or generic platforms (e.g. a "best apps" article's publisher, Android, Google Play) unless the text describes them as offering a competing product.
- Order them by how directly they compete, closest first.
- If the results name no real competitors, return an empty list. Never add a competitor from your own knowledge.

Step 2 - profile each competitor, using ONLY the result text:
- "name": exactly as written in the text
- "sourceIds": the ids of the results that mention it
- "offering": one short sentence on what it offers, from the text
- "classification": "direct" (solves the same problem for the same customer), "indirect" (different product or customer that still competes for the same need), or "unknown"
- "pricing": a short note of the pricing the text states (e.g. "$12/mo, free tier"), or "unknown"
- "businessModel": how it makes money if the text says (e.g. "subscription", "marketplace commission"), or "unknown"
- "strengths": 0-3 short phrases the text supports
- "weaknesses": 0-3 short phrases the text supports (complaints, missing features, limits)
- "gap": one sentence on where THIS startup idea could beat or differ from this competitor, grounded in the weaknesses or the text

Step 3 - build "comparisonMatrix": 3-5 rows comparing the startup idea against these competitors on dimensions that matter to the target customer (e.g. price, core feature, target user, ease of setup). Each row: "dimension", "idea" (how the startup idea approaches it), and "competitors" (an object keyed by the exact competitor names from Step 1; use "unknown" where the text is silent). Omit the matrix if Step 1 found no competitors.
