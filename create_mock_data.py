important_details = [
    "property_address",
    "city_state_zip",
    "mls_number",
    "listing_agent_name",
    "buyer_names",
    "listing_price",
    "offer_price",
    "earnest_money_amount",
    "closing_date",
    "appraisal_terms",
]

data = {
    "property_address": [
        "1426 Maple St",
        "815 Cedar Ave",
        "2231 Lakeview Dr",
        "77 Oak Ridge Ct",
        "509 Pinecrest Way",
        "1901 Willow Bend Rd",
        "8642 Birch Ln",
        "330 Juniper Trl",
        "58 Spruce Terrace",
        "1200 Elmwood Pl",
    ],
    "city_state_zip": [
        "Austin, TX 78704",
        "Denver, CO 80211",
        "Seattle, WA 98116",
        "Portland, OR 97214",
        "Phoenix, AZ 85018",
        "San Diego, CA 92103",
        "Atlanta, GA 30307",
        "Chicago, IL 60657",
        "Nashville, TN 37212",
        "Raleigh, NC 27608",
    ],
    "mls_number": [
        "9876543210", "1100223344", "5600987612", "4433219900", "7733114499",
        "2200456677", "9098776611", "3322115599", "7788990011", "6655443322",
    ],
    "listing_agent_name": [
        "Taylor Brooks",
        "Jordan Kim",
        "Alexis Rivera",
        "Morgan Patel",
        "Casey Nguyen",
        "Riley Thompson",
        "Jamie Alvarez",
        "Samira Hassan",
        "Devon Lee",
        "Priya Shah",
    ],
    "buyer_names": [
        "Alex & Jamie Chen",
        "Priya and Arjun Desai",
        "Maria Lopez",
        "Chris and Taylor Reed",
        "Jordan Singh",
        "Fatima Khan",
        "Emily and Mark Davis",
        "Noah Martinez",
        "Sophia Russo",
        "Liam O'Connor",
    ],
    "listing_price": [
        550000, 675000, 795000, 625000, 710000, 885000, 540000, 760000, 640000, 720000
    ],
    "offer_price": [
        565000, 689000, 810000, 640000, 725000, 905000, 555000, 775000, 652500, 735000
    ],
    "earnest_money_amount": [
        15000, 20000, 25000, 15000, 20000, 30000, 12000, 18000, 16000, 20000
    ],
    "closing_date": [
        "2025-11-15", "2025-12-01", "2025-11-30", "2025-11-20", "2025-12-05",
        "2025-11-25", "2025-12-10", "2025-11-28", "2025-12-03", "2025-11-22",
    ],
    "appraisal_terms": [
        "Gap coverage up to $10,000",
        "Kept; standard appraisal",
        "Waived with strong comps",
        "Gap coverage up to $7,500",
        "Kept; lender ordered rush",
        "Waived (cash-like strength)",
        "Kept; buyer covers first $5,000 shortfall",
        "Gap coverage up to $12,000",
        "Kept; local lender prioritizing",
        "Waived with proof of funds",
    ],
}

# Sanity check: ensure all arrays are length 10 and keys exist
for k in important_details:
    assert k in data, f"Missing data for key: {k}"
    assert len(data[k]) == 10, f"{k} does not have 10 example values"

# --- System prompt builder (f-string) ---
def select_mock_data(index: int = 0) -> dict:
    return {k: data[k][index] for k in important_details}

def build_system_prompt(d: dict) -> str:
    system_prompt = f"""
You are an AI negotiation agent representing the buyer(s) {d['buyer_names']} for the property at {d['property_address']}, {d['city_state_zip']} (MLS {d['mls_number']}).
You will communicate with the listing agent {d['listing_agent_name']}.

OBJECTIVE
- Persuade the listing side to accept the buyer's offer at {d['offer_price']:,} USD on {d['property_address']} while maintaining professionalism, ethics, and compliance.

ESSENTIAL OFFER SUMMARY (include up front in messages)
- List Price: {d['listing_price']:,} USD
- Offer Price: {d['offer_price']:,} USD
- Earnest Money: {d['earnest_money_amount']:,} USD
- Closing Date: {d['closing_date']}
- Appraisal Terms: {d['appraisal_terms']}

TACTICS (ethical & effective)
1) Certainty of Close:
   - Highlight earnest money of {d['earnest_money_amount']:,} USD.
2) Speed & Simplicity:
   - Stress the clean, straightforward terms and targeted closing date ({d['closing_date']}).
3) Professional Tone:
   - Be concise, warm, and solutions-oriented. Avoid pressure; propose practical next steps.
4) Objection Handling:
   - Appraisal concerns → restate: {d['appraisal_terms']}.
   - Competing offers → emphasize certainty, clean terms, and readiness to proceed.

COMPLIANCE & INTEGRITY (must follow)
- Be truthful. Do not fabricate facts, documents, or competing offer details.
- Comply with Fair Housing: never reference protected classes, demographics, schools, or buyer personal attributes unrelated to the transaction.
- Avoid “love letter” content; focus on offer strength and logistics.
- Keep communications respectful and non-harassing.

OUTPUT STYLE
- You are on a PHONE CALL with {d['listing_agent_name']}. Keep all responses BRIEF (under 50 words).
- Write responses naturally and conversationally as if in a real-time phone conversation.
- Avoid stating large amounts of information verbatim unless it's specifically important or the listing agent asks about it.
- Focus on the key points that move the negotiation forward.
- Address likely objections proactively but concisely.
- Ask for a clear next step when appropriate.
- Do not use emojis.

FACTS YOU MAY INCLUDE VERBATIM IF RELEVANT TO THE CONVERSATION
- Property: {d['property_address']}, {d['city_state_zip']} (MLS {d['mls_number']})
- List: {d['listing_price']:,} • Offer: {d['offer_price']:,} • Earnest: {d['earnest_money_amount']:,}
- Closing: {d['closing_date']} • Appraisal: {d['appraisal_terms']}

Default to clarity, brevity, and confidence.
"""
    return system_prompt.strip()

# --- Demo: print the trimmed list of options and one generated system prompt ---
if __name__ == "__main__":
    print(important_details)
    print("--- System Prompt ---")
    print(build_system_prompt(select_mock_data(0)))
