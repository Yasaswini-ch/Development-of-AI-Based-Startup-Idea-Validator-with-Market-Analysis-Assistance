Startup idea being validated: "{idea}"
Target customer: {target_customer}
Problem: {problem}

Live search results about competitors and existing solutions, each with an id:
{listing}

Names an automatic entity tagger picked out of these results (may be incomplete, and may include publishers, platforms or other non-competitors): {ner_hints}

Step 1 - find competitors. List up to {max_competitors} companies or products that a customer could use instead of this startup idea to solve the same need. Rules:
- Prefer names written in the text of a result above, spelled as they appear there - but you may also include a real, well-known competitor you recognize for this category even if no result above happens to name it, as long as you cite the sourceId of whichever result is most relevant to it.
- Do not include publishers, review sites, news outlets, app stores, operating systems or generic platforms (e.g. a "best apps" article's publisher, Android, Google Play) unless the text describes them as offering a competing product.
- Order them by how directly they compete, closest first.
- If you genuinely can't identify any real competitors for this category, return an empty list rather than inventing one.

Step 2 - profile each competitor, grounded in the result text where it's available and your own knowledge of the category where it isn't:
- "name": the competitor's real name
- "sourceIds": the ids of the results that mention it, or the single most relevant result id if none do
- "offering": 2-3 sentences on what it actually offers - be specific about its core workflow, not a generic tagline
- "classification": "direct" (solves the same problem for the same customer), "indirect" (different product or customer that still competes for the same need), or "unknown"
- "pricing": what it costs (e.g. "$12/mo, free tier") if known, or "unknown"
- "businessModel": how it makes money (e.g. "subscription", "marketplace commission") if known, or "unknown"
- "strengths": up to 5 specific phrases - real capabilities, not vague praise
- "weaknesses": up to 5 specific phrases (complaints, missing features, limits) - real gaps, not vague criticism
- "gap": 2-3 sentences on where THIS startup idea could beat or differ from this competitor - be concrete about the mechanism, not just "it's better"

Step 3 - build "comparisonMatrix": 5-8 rows comparing the startup idea against these competitors on dimensions that matter to the target customer (price, core feature, target user, ease of setup, integration/ecosystem, support, and anything else genuinely differentiating for this category). Each row: "dimension", "idea" (2-3 sentences on how the startup idea approaches it), and "competitors" (an object keyed by the exact competitor names from Step 1, each 1-2 sentences; use "unknown" only where you truly have no basis for a value). Omit the matrix if Step 1 found no competitors.
