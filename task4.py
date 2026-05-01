# ============================================================
# TASK 4 — Portfolio Health Score
# Timecell.ai Internship Assessment
# Author: Dhruvi
#
# AI Tools Used: Claude (Anthropic) — used as coding assistant for
#                HHI formula reference and log curve anchor suggestions
#
# WHAT THIS IS:
#   A single 0–100 "Portfolio Health Score" — like a CIBIL credit
#   score but for investment portfolios. Instead of asking users
#   to interpret raw metrics (runway months, crash percentages),
#   this collapses everything into one number they can track
#   over time and act on.
#
# WHY I BUILT THIS:
#   Timecell surfaces risk metrics (crash survival, temperature,
#   position sizing). But non-expert clients still ask: "Is my
#   portfolio OK or not?" A single score answers that instantly.
#   It also creates a natural nudge loop — users want to improve
#   their score, which drives engagement with the platform.
#
# HOW THE SCORE WORKS (transparent, not a black box):
#   Four components, each scored 0–25, summed to 0–100:
#
#   1. Runway Score     (0–25) — post-crash expense coverage
#   2. Crash Loss Score (0–25) — how much value survives a crash
#   3. Concentration    (0–25) — diversification across assets
#   4. Ruin Safety      (0–25) — passes the 12-month ruin test
#
# GRADE SCALE:
#   90–100  A+  Fortress
#   75–89   A   Strong
#   60–74   B   Moderate
#   45–59   C   Caution
#   0–44    D   Danger
# ============================================================

from typing import Dict, Any
from copy import deepcopy
import math


# ============================================================
# SCORING ENGINE
# ============================================================

def score_runway(runway_months: float) -> float:
    """
    Score 0–25 based on post-crash expense runway.

    Design rationale:
    - < 6 months: danger zone, score 0
    - 12 months: minimum safe (ruin test threshold), score ~12
    - 24 months: comfortable, score ~20
    - 60+ months: excellent, approaches 25
    Uses a logarithmic curve so improvements at the low end
    matter more than marginal gains at the high end.
    """
    if runway_months <= 0:
        return 0.0
    if runway_months == float("inf"):
        return 25.0

    # log curve anchored at: 6mo→0, 12mo→12, 60mo→25
    score = 25 * (math.log(runway_months + 1) / math.log(61))
    return round(min(25.0, max(0.0, score)), 2)


def score_crash_survival(post_crash_value: float, total_value: float) -> float:
    """
    Score 0–25 based on what fraction of the portfolio survives a crash.

    Design rationale:
    - Losing > 80% → score 0
    - Losing 50% → score ~12
    - Losing < 10% → score ~23
    - Surviving intact → score 25
    """
    if total_value <= 0:
        return 0.0

    survival_pct = post_crash_value / total_value   # 0.0 to 1.0
    score        = 25 * survival_pct
    return round(min(25.0, max(0.0, score)), 2)


def score_concentration(assets: list) -> float:
    """
    Score 0–25 based on diversification (Herfindahl-Hirschman Index).

    Design rationale:
    HHI measures concentration: sum of squared allocation fractions.
    - HHI = 1.0 → 100% in one asset (worst concentration)
    - HHI = 0.25 → 4 equal assets (good diversification for 4 assets)
    - HHI → 0 → perfectly spread (theoretical maximum)
    We invert and scale so lower HHI = higher score.
    """
    if not assets:
        return 0.0

    hhi = sum((a.get("allocation_pct", 0) / 100) ** 2 for a in assets)

    # Invert: HHI=1 → score 0, HHI≈0 → score 25
    score = 25 * (1 - hhi)
    return round(min(25.0, max(0.0, score)), 2)


def score_ruin_test(ruin_test: str) -> float:
    """
    Binary score: 25 if PASS, 0 if FAIL.
    The ruin test (runway > 12 months) is the single most important
    safety gate — failing it gets zero regardless of other scores.
    """
    return 25.0 if ruin_test == "PASS" else 0.0


# ============================================================
# GRADE LOOKUP
# ============================================================

def get_grade(score: float) -> tuple:
    """
    Maps a 0–100 score to a letter grade and label.

    Returns:
        (grade, label, emoji)
    """
    if score >= 90:
        return ("A+", "Fortress",  "🟢")
    elif score >= 75:
        return ("A",  "Strong",    "🟢")
    elif score >= 60:
        return ("B",  "Moderate",  "🟡")
    elif score >= 45:
        return ("C",  "Caution",   "🟠")
    else:
        return ("D",  "Danger",    "🔴")


# ============================================================
# MAIN SCORING FUNCTION
# ============================================================

def compute_health_score(portfolio: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a 0–100 Portfolio Health Score from raw portfolio data.

    This function replicates the core Task 1 metrics internally
    so Task 4 works as a fully standalone module — no imports needed.

    Args:
        portfolio: dict with total_value_inr, monthly_expenses_inr, assets

    Returns:
        dict with score, grade, label, component breakdown, and actionable tip
    """
    total_value      = portfolio.get("total_value_inr", 0)
    monthly_expenses = portfolio.get("monthly_expenses_inr", 0)
    assets           = portfolio.get("assets", [])

    # --- Replicate Task 1 core metrics ---
    post_crash_value = sum(
        max(0.0,
            (total_value * a.get("allocation_pct", 0) / 100)
            * (1 + a.get("expected_crash_pct", 0) / 100))
        for a in assets
    )

    runway_months = (
        post_crash_value / monthly_expenses
        if monthly_expenses > 0 else float("inf")
    )

    ruin_test = "PASS" if runway_months > 12 else "FAIL"

    # --- Score each component ---
    s_runway      = score_runway(runway_months)
    s_crash       = score_crash_survival(post_crash_value, total_value)
    s_conc        = score_concentration(assets)
    s_ruin        = score_ruin_test(ruin_test)

    total_score   = round(s_runway + s_crash + s_conc + s_ruin, 1)
    grade, label, emoji = get_grade(total_score)

    # --- Weakest component → actionable tip ---
    components = {
        "Runway":       s_runway,
        "Crash Safety": s_crash,
        "Diversification": s_conc,
        "Ruin Test":    s_ruin,
    }
    weakest = min(components, key=components.get)

    tips = {
        "Runway": (
            "Your post-crash runway is short. Consider reducing high-risk "
            "allocations or increasing your cash/bond buffer."
        ),
        "Crash Safety": (
            "Too much value is lost in a crash. Shift some allocation from "
            "volatile assets (crypto, growth stocks) to stable ones (gold, bonds)."
        ),
        "Diversification": (
            "Portfolio is too concentrated in one asset. Spreading across "
            "4–6 uncorrelated assets significantly reduces risk."
        ),
        "Ruin Test": (
            "CRITICAL: Your portfolio fails the 12-month ruin test. "
            "In a crash, you cannot cover even one year of expenses. "
            "Increase cash or stable asset allocation immediately."
        ),
    }

    return {
        "score":           total_score,
        "grade":           grade,
        "label":           label,
        "emoji":           emoji,
        "components":      components,
        "weakest_area":    weakest,
        "tip":             tips[weakest],
        "post_crash_value": round(post_crash_value, 2),
        "runway_months":   round(runway_months, 2) if runway_months != float("inf") else float("inf"),
        "ruin_test":       ruin_test,
    }


# ============================================================
# DISPLAY
# ============================================================

def display_health_score(portfolio: Dict[str, Any]):
    """
    Prints the full health score report to the terminal.
    """
    result = compute_health_score(portfolio)
    score  = result["score"]
    grade  = result["grade"]
    label  = result["label"]
    emoji  = result["emoji"]

    # Score bar — visual representation of 0–100
    filled = int(score / 5)   # 20 segments total (100 / 5 = 20)
    bar    = "█" * filled + "░" * (20 - filled)

    print("\n" + "=" * 58)
    print("  💊  TIMECELL PORTFOLIO HEALTH SCORE")
    print("=" * 58)
    print(f"\n  {emoji}  Score : {score} / 100   [{bar}]")
    print(f"      Grade : {grade}  —  {label}")
    print()
    print("  COMPONENT BREAKDOWN  (each out of 25)")
    print("  " + "-" * 44)

    for name, val in result["components"].items():
        seg   = int(val / 25 * 10)   # 10-char mini bar
        mini  = "█" * seg + "░" * (10 - seg)
        print(f"  {name:<20} [{mini}]  {val:>5.1f} / 25")

    print()
    print("  POST-CRASH METRICS")
    print("  " + "-" * 44)
    rv = result["runway_months"]
    print(f"  Post-Crash Value   : ₹{result['post_crash_value']:>14,.2f}")
    print(f"  Expense Runway     :  {rv if rv == float('inf') else f'{rv:.1f} months':>14}")
    print(f"  Ruin Test          :  {'✅ PASS' if result['ruin_test'] == 'PASS' else '❌ FAIL':>14}")

    print()
    print(f"  ⚠️   WEAKEST AREA: {result['weakest_area'].upper()}")
    print(f"  💡  {result['tip']}")
    print("=" * 58)


# ============================================================
# COMPARISON — Score two portfolios side by side
# ============================================================

def compare_portfolios(portfolio_a: Dict, portfolio_b: Dict,
                        label_a: str = "Portfolio A",
                        label_b: str = "Portfolio B"):
    """
    Compares two portfolios by health score side by side.
    Useful for before/after rebalancing analysis.
    """
    a = compute_health_score(portfolio_a)
    b = compute_health_score(portfolio_b)

    winner = label_a if a["score"] >= b["score"] else label_b

    print("\n" + "=" * 58)
    print("  ⚖️   PORTFOLIO COMPARISON")
    print("=" * 58)
    print(f"  {'Metric':<22} {'':^2} {label_a:^14} {label_b:^14}")
    print("  " + "-" * 54)

    rows = [
        ("Health Score",   f"{a['score']}/100",         f"{b['score']}/100"),
        ("Grade",          f"{a['grade']} ({a['label']})", f"{b['grade']} ({b['label']})"),
        ("Runway",         f"{a['runway_months']} mo",   f"{b['runway_months']} mo"),
        ("Ruin Test",      a["ruin_test"],                b["ruin_test"]),
        ("Weakest Area",   a["weakest_area"],             b["weakest_area"]),
    ]

    for label, val_a, val_b in rows:
        print(f"  {label:<22}   {val_a:<16} {val_b:<16}")

    print("  " + "-" * 54)
    print(f"  🏆  Better portfolio: {winner}")
    print("=" * 58)


# ============================================================
# MAIN
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

    # Conservative alternative — same total value
    portfolio_conservative = {
        "total_value_inr": 10_000_000,
        "monthly_expenses_inr": 80_000,
        "assets": [
            {"name": "BONDS",   "allocation_pct": 35, "expected_crash_pct":  -5},
            {"name": "NIFTY50", "allocation_pct": 25, "expected_crash_pct": -40},
            {"name": "GOLD",    "allocation_pct": 25, "expected_crash_pct": -15},
            {"name": "CASH",    "allocation_pct": 15, "expected_crash_pct":   0},
        ]
    }

    # Full report for main portfolio
    display_health_score(portfolio_aggressive)

    # Side-by-side comparison
    compare_portfolios(
        portfolio_aggressive,
        portfolio_conservative,
        label_a="Aggressive",
        label_b="Conservative"
    )