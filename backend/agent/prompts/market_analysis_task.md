Startup idea: "{idea}"
Target customer: {target_customer}
Problem being solved: {problem}

Here are real, current web search results about this idea's market. Each one is tagged with a sourceId like [src-1]:
{context}

Based only on the information above, analyze:
1. Market size (state whether the figures are global, regional, or niche if the sources indicate this) and growth trend. Include TAM, SAM, or CAGR only when the provided sources explicitly support those figures; otherwise state that they are not clear from the sources.
1b. Separately, TAM (Total Addressable Market), SAM (Serviceable Addressable Market), and SOM (Serviceable Obtainable Market) as three distinct figures, each with a "sourceIds" array the same way as for trends below. Set any of the three to null (not a guessed number) whenever the sources don't explicitly support that specific figure - never derive one tier's number from another or estimate a plausible-looking value.
2. Up to 4 notable trends or adoption patterns. Each trend needs a "sourceIds" array citing the sourceId(s) of the source(s) shown above that it's grounded in - use an empty array only when a trend is a structural observation not tied to a specific source, never invent a sourceId that isn't shown above.
3. Up to 4 customer segments - for each, their pain points (what problem they're trying to solve), motivations (what they care about / why they'd buy), buying behavior (how they decide or purchase, if the sources suggest anything about this), and a "sourceIds" array the same way as for trends.
Do not invent statistics, segments, or behaviors that aren't supported by the sources - if buying behavior isn't evident from the sources, say so plainly rather than guessing.
Output strict JSON only: within JSON strings, never escape an apostrophe with a backslash - write don't directly, not don\'t.
