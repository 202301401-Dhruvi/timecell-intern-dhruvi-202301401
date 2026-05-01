# ============================================================
# TASK 3 — AI-Powered Portfolio Explainer
# Timecell.ai Internship Assessment
# Author: Dhruvi
#
# AI Tools Used: Claude (Anthropic) — used as coding assistant
#                Google Gemini — LLM API provider for portfolio analysis
#
# WHY GEMINI?
#   Free tier requires no credit card — ideal for a 72-hour assessment.
#   Gemini 2.5 Flash is fast, accurate, and handles structured JSON well.
#   The prompt engineering principles are identical regardless of provider.
#
# SETUP:
#   pip install google-generativeai python-dotenv
#   Create a .env file with ONE line (no spaces around =):
#   GEMINI_API_KEY=your-key-here
#   Get a free key at: https://aistudio.google.com
# ============================================================

import google.generativeai as genai
import os
import json
import re
import time
from typing import Optional
from dotenv import load_dotenv

load_dotenv()   # Reads .env file into os.environ


# ============================================================
# PROMPT ENGINEERING — The heart of this task
# ============================================================

def build_system_prompt(tone: str = "beginner") -> str:
    """
    Builds a system prompt tailored to the investor's experience level.

    PROMPT ENGINEERING DECISIONS:
    1. Clear ROLE definition ("senior financial advisor") anchors the model's
       tone and prevents generic, wishy-washy responses.
    2. Explicit OUTPUT FORMAT rules with a JSON template eliminate ambiguity.
    3. Tone levels mean the same pipeline serves complete beginners AND
       expert family-office CIOs — the core Timecell use case.
    4. "Speak as 'you'" prevents impersonal financial-report language.
    5. Pre-computing all metrics in the user message reduces LLM math errors.

    Args:
        tone: 'beginner', 'experienced', or 'expert'

    Returns:
        str: System prompt string
    """

    tone_instructions = {
        "beginner": """
You are explaining to someone who has NEVER invested before.
- Use simple everyday language. Zero jargon.
- If you must use a financial term, immediately explain it in plain brackets.
- Use relatable analogies (e.g. "like putting all your eggs in one basket").
- Be warm, encouraging, and non-scary — investing feels overwhelming to beginners.
        """,

        "experienced": """
You are explaining to someone who understands investing basics like
diversification, volatility, and asset classes.
- Use standard financial terminology without over-explaining.
- Be direct and professional.
- Reference concepts like drawdown, beta, or rebalancing freely.
        """,

        "expert": """
You are explaining to a sophisticated investor or family-office CIO.
- Be concise and technical. No hand-holding.
- Reference advanced concepts freely: tail risk, Kelly criterion,
  max drawdown, volatility-adjusted returns, concentration limits.
- Focus on quantitative implications, not narrative.
        """
    }

    tone_text = tone_instructions.get(tone, tone_instructions["beginner"])

    return f"""
You are a senior financial advisor at a wealth management firm serving
high-net-worth Indian families. You are honest, direct, and always
prioritise your client's long-term financial safety.

TONE LEVEL: {tone.upper()}
{tone_text}

OUTPUT FORMAT — You MUST respond with ONLY a valid JSON object.
No text before or after the JSON. No markdown code fences. Nothing else.

The JSON must have EXACTLY these 4 keys:
{{
  "summary": "<3-4 sentence plain-English overview of the portfolio risk>",
  "doing_well": "<ONE specific strength, with a brief reason why it matters>",
  "consider_changing": "<ONE specific change to consider, and a clear reason why>",
  "verdict": "<MUST be exactly one of: Aggressive | Balanced | Conservative>"
}}

STRICT RULES:
- Base analysis ONLY on the numbers given. Do not invent data.
- verdict must be one word: Aggressive, Balanced, or Conservative.
- Reference actual asset names and percentages — be specific.
- Address the client directly as "you", never "the investor".
- Keep each field concise and actionable.
""".strip()


def build_user_message(portfolio: dict) -> str:
    """
    Builds the user message with portfolio data and pre-computed metrics.

    PROMPT ENGINEERING DECISIONS:
    - Structured prose format is more readable to LLMs than raw Python dicts.
    - Pre-computing crash value, runway, and risk scores prevents the LLM
      from doing mental arithmetic — the main source of numeric errors.
    - Flagging concentration risk explicitly ensures the model notices it.

    Args:
        portfolio: Portfolio dictionary (same structure as Task 1)

    Returns:
        str: Formatted user message
    """
    total    = portfolio.get("total_value_inr", 0)
    expenses = portfolio.get("monthly_expenses_inr", 0)
    assets   = portfolio.get("assets", [])

    # Pre-compute all metrics so the LLM doesn't have to
    post_crash_value = sum(
        (total * a.get("allocation_pct", 0) / 100)
        * (1 + a.get("expected_crash_pct", 0) / 100)
        for a in assets
    )

    runway = post_crash_value / expenses if expenses > 0 else float("inf")

    largest_risk = max(
        assets,
        key=lambda a: a.get("allocation_pct", 0) * abs(a.get("expected_crash_pct", 0)),
        default={}
    )

    asset_lines = "\n".join(
        f"  - {a.get('name', 'Unknown')}: {a.get('allocation_pct', 0)}% allocation, "
        f"expected crash: {a.get('expected_crash_pct', 0)}%"
        for a in assets
    )

    concentration_flag = (
        "YES — at least one asset exceeds 40% allocation"
        if any(a.get("allocation_pct", 0) > 40 for a in assets)
        else "NO"
    )

    return f"""
Please analyse this portfolio and respond in the JSON format specified.

PORTFOLIO DETAILS:
  Total Value      : Rs.{total:,.0f} INR
  Monthly Expenses : Rs.{expenses:,.0f} INR

ASSET BREAKDOWN:
{asset_lines}

PRE-COMPUTED METRICS (verified — use these directly):
  Post-crash value   : Rs.{post_crash_value:,.0f} INR
  Expense runway     : {runway:.1f} months post-crash
  Highest risk asset : {largest_risk.get('name', 'N/A')} \
({largest_risk.get('allocation_pct', 0)}% x \
{abs(largest_risk.get('expected_crash_pct', 0))}% crash \
= {largest_risk.get('allocation_pct', 0) * abs(largest_risk.get('expected_crash_pct', 0))} risk score)
  Concentration risk : {concentration_flag}

Now provide your structured JSON analysis.
""".strip()


# ============================================================
# API CALL — Google Gemini with retry + rate-limit back-off
# ============================================================

def call_gemini_api(system_prompt: str, user_message: str,
                    max_retries: int = 3) -> str:
    """
    Calls the Google Gemini API with exponential back-off retry logic.

    Includes a mock fallback when no API key is set so the script
    always demonstrates its structure cleanly.

    DESIGN NOTES:
    - gemini-1.5-flash is the stable free-tier model. We avoid
      gemini-2.0-flash here because it has a stricter per-day cap
      on the free tier that is harder to recover from automatically.
    - Exponential back-off (35s → 65s → 120s) covers the per-minute
      quota reset window without manual intervention.
    - max_retries=3 with long waits handles transient rate-limit errors.

    Args:
        system_prompt:  Role/rules/format instructions
        user_message:   Portfolio data with pre-computed metrics
        max_retries:    Number of retry attempts on failure

    Returns:
        str: Raw text response from Gemini
    """
    api_key = os.environ.get("GEMINI_API_KEY")

    # --- Fallback: demo mode without API key ---
    if not api_key:
        print("  ⚠️  No API key found — using mock response for demonstration\n")
        return json.dumps({
            "summary": (
                "Your portfolio carries significant risk with 30% in Bitcoin, "
                "which could lose up to 80% of its value in a crash. "
                "However, your post-crash runway of 71 months means you can "
                "cover expenses for nearly 6 years even in a worst-case scenario. "
                "The mix of assets provides some protection but leans aggressive."
            ),
            "doing_well": (
                "You hold 10% in cash and 20% in gold — these act as a safety "
                "cushion that keeps your runway well above the 12-month minimum."
            ),
            "consider_changing": (
                "Your 30% Bitcoin allocation carries the highest risk in the portfolio. "
                "Reducing it to 15% and moving the difference to NIFTY50 or bonds "
                "would significantly lower your crash exposure while keeping growth potential."
            ),
            "verdict": "Aggressive"
        }, indent=2)

    # --- Configure Gemini ---
    genai.configure(api_key=api_key)

    # gemini-1.5-flash: stable, free-tier, reliable for structured JSON output
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt
    )

    # --- Retry loop with exponential back-off ---
    # Free tier resets per minute — waiting 35s clears per-minute quota
    wait_times = [35, 65, 120]
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(user_message)
            return response.text

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = wait_times[attempt - 1]
                print(f"  ↩️  Rate limit hit (attempt {attempt}/{max_retries}) "
                      f"— waiting {wait}s for quota reset...")
                time.sleep(wait)

    raise RuntimeError(f"Gemini API failed after {max_retries} attempts: {last_error}")


# ============================================================
# BONUS — Second Gemini call to critique the first explanation
# ============================================================

def call_critique_api(original_analysis: dict, portfolio: dict) -> str:
    """
    BONUS: A second Gemini call that independently fact-checks the first.

    PROMPT ENGINEERING NOTE:
    This is a real production technique called "critic-actor architecture".
    The first call generates the analysis; the second independently checks
    it for accuracy. This catches cases where the model's reasoning drifts
    from the actual numbers provided.

    Args:
        original_analysis: Parsed JSON dict from first call
        portfolio:         Original portfolio dict

    Returns:
        str: Critique text (2-3 sentences)
    """
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return "Critique skipped — no API key set."

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    critique_prompt = f"""
You are an independent fact-checker reviewing a financial advisor's analysis.

ORIGINAL PORTFOLIO:
{json.dumps(portfolio, indent=2)}

ANALYSIS TO REVIEW:
{json.dumps(original_analysis, indent=2)}

Check specifically:
1. Mathematical accuracy — do the claims match the numbers?
2. Logical consistency — does the verdict match the summary?
3. Actionability — is the advice specific and useful?

Respond in exactly 2-3 sentences. Be direct. Clearly flag any inaccuracies.
If the analysis is fully accurate, confirm that briefly.
""".strip()

    try:
        # Wait before second call to avoid back-to-back rate limit hits
        print("  ⏳  Waiting 35s before critique call to respect rate limits...")
        time.sleep(35)
        response = model.generate_content(critique_prompt)
        return response.text
    except Exception as e:
        return f"Critique failed: {e}"


# ============================================================
# PARSER — Extract structured output from raw API response
# ============================================================

def parse_response(raw_response: str) -> Optional[dict]:
    """
    Parses the raw Gemini response into a structured Python dict.

    Defensively strips markdown code fences — Gemini often adds them
    even when told not to.

    Args:
        raw_response: Raw string from Gemini API

    Returns:
        dict with keys: summary, doing_well, consider_changing, verdict
        or None if parsing fails
    """
    # Strip markdown fences aggressively
    cleaned = re.sub(r"```(?:json)?.*?```", "", raw_response, flags=re.DOTALL)
    cleaned = re.sub(r"```", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        print(f"  Raw response:\n{raw_response}")
        return None

    # Validate required keys
    required_keys = {"summary", "doing_well", "consider_changing", "verdict"}
    missing = required_keys - parsed.keys()
    if missing:
        print(f"  ⚠️  Missing keys in response: {missing}")
        return None

    # Validate and auto-correct verdict
    allowed_verdicts = {"Aggressive", "Balanced", "Conservative"}
    if parsed["verdict"] not in allowed_verdicts:
        print(f"  ⚠️  Invalid verdict '{parsed['verdict']}' — defaulting to 'Balanced'")
        parsed["verdict"] = "Balanced"

    return parsed


# ============================================================
# DISPLAY — Pretty print structured output
# ============================================================

def display_analysis(parsed: dict, tone: str):
    """
    Prints the structured analysis in a clean, readable terminal format.
    """
    verdict_emoji = {
        "Aggressive":   "🔴",
        "Balanced":     "🟡",
        "Conservative": "🟢"
    }
    emoji = verdict_emoji.get(parsed["verdict"], "⚪")

    print("\n" + "=" * 62)
    print(f"  🤖  AI PORTFOLIO ANALYSIS  |  Tone: {tone.upper()}")
    print("=" * 62)
    print(f"\n  📋  SUMMARY")
    print(f"  {parsed['summary']}")
    print(f"\n  ✅  WHAT YOU'RE DOING WELL")
    print(f"  {parsed['doing_well']}")
    print(f"\n  ⚠️   WHAT TO CONSIDER CHANGING")
    print(f"  {parsed['consider_changing']}")
    print(f"\n  {emoji}  VERDICT: {parsed['verdict'].upper()}")
    print("=" * 62)


# ============================================================
# MAIN PIPELINE — Accepts any portfolio, any tone
# ============================================================

def explain_portfolio(portfolio: dict, tone: str = "beginner",
                      run_critique: bool = True):
    """
    Full pipeline: validate → build prompts → call API → parse → display.

    Args:
        portfolio:    Portfolio dictionary (same structure as Task 1)
        tone:         'beginner', 'experienced', or 'expert'
        run_critique: Whether to run the bonus second-pass critique
    """

    # --- Input validation ---
    if not portfolio or "assets" not in portfolio or not portfolio["assets"]:
        print("  ❌  Invalid portfolio: must have at least one asset.")
        return

    print(f"\n  🔄  Sending portfolio to Gemini API  (tone: {tone})...")

    # --- Build prompts ---
    system_prompt = build_system_prompt(tone)
    user_message  = build_user_message(portfolio)

    # --- Call API ---
    try:
        raw_response = call_gemini_api(system_prompt, user_message)
    except RuntimeError as e:
        print(f"\n  ❌  {e}")
        return

    # --- Show RAW response (required by assignment) ---
    print("\n" + "=" * 62)
    print("  📡  RAW API RESPONSE  (unparsed, exactly as received)")
    print("=" * 62)
    print(raw_response)

    # --- Parse structured output ---
    parsed = parse_response(raw_response)
    if parsed is None:
        print("  ❌  Could not parse structured output.")
        return

    # --- Display structured output (required by assignment) ---
    display_analysis(parsed, tone)

    # --- BONUS: Critique pass ---
    if run_critique:
        print("\n  🔍  Running critique pass (Bonus — second LLM call)...")
        critique = call_critique_api(parsed, portfolio)
        print("\n" + "=" * 62)
        print("  🧠  CRITIQUE  (Second Gemini pass — fact-checks the first)")
        print("=" * 62)
        print(f"\n  {critique}")
        print("=" * 62)


# ============================================================
# MAIN — Two portfolios, two tones
# ============================================================

if __name__ == "__main__":

    # Portfolio from the assignment (aggressive)
    portfolio_aggressive = {
        "total_value_inr": 10_000_000,
        "monthly_expenses_inr": 80_000,
        "assets": [
            {"name": "BTC",     "allocation_pct": 30, "expected_crash_pct": -80},
            {"name": "NIFTY50", "allocation_pct": 40, "expected_crash_pct": -40},
            {"name": "GOLD",    "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "CASH",    "allocation_pct": 10, "expected_crash_pct":   0},
        ]
    }

    # Second portfolio — conservative (shows script works with any input)
    portfolio_conservative = {
        "total_value_inr": 5_000_000,
        "monthly_expenses_inr": 50_000,
        "assets": [
            {"name": "GOLD",    "allocation_pct": 30, "expected_crash_pct": -15},
            {"name": "BONDS",   "allocation_pct": 40, "expected_crash_pct":  -5},
            {"name": "NIFTY50", "allocation_pct": 20, "expected_crash_pct": -40},
            {"name": "CASH",    "allocation_pct": 10, "expected_crash_pct":   0},
        ]
    }

    # Run 1: Aggressive portfolio, beginner tone, with critique
    explain_portfolio(portfolio_aggressive, tone="beginner", run_critique=True)

    print("\n\n")

    # Run 2: Conservative portfolio, experienced tone, no critique
    explain_portfolio(portfolio_conservative, tone="experienced", run_critique=False)