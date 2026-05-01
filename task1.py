# ============================================================
# TASK 1 — Portfolio Risk Calculator
# Timecell.ai Internship Assessment
# Author: Dhruvi
# AI Tools Used: Claude (Anthropic),chatgpt — used for code structure,
#                edge case identification, and type hint guidance
# ============================================================

"""
Assumptions:
- Allocation percentages should sum to ~100%
- Crash percentages are negative values representing loss
- Post-crash value of any single asset cannot go below zero
- Runway is infinite if monthly expenses are zero
"""

from typing import Dict, Any
from copy import deepcopy


# ============================================================
# CORE FUNCTION
# ============================================================

def compute_risk_metrics(portfolio: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes key risk metrics for a given portfolio.

    Args:
        portfolio: dict with keys:
            - total_value_inr (float)
            - monthly_expenses_inr (float)
            - assets (list of dicts: name, allocation_pct, expected_crash_pct)

    Returns:
        dict with:
            - post_crash_value: portfolio value after crash scenario
            - runway_months: months of expenses covered post-crash
            - ruin_test: 'PASS' if runway > 12, else 'FAIL'
            - largest_risk_asset: asset with highest risk impact score
            - concentration_warning: True if any asset > 40% allocation
    """

    # --- Safe extraction with defaults ---
    total_value      = portfolio.get("total_value_inr", 0)
    monthly_expenses = portfolio.get("monthly_expenses_inr", 0)
    assets           = portfolio.get("assets", [])

    # --- Edge case: empty or zero-value portfolio ---
    if not assets or total_value <= 0:
        return {
            "post_crash_value":      0,
            "runway_months":         0,
            "ruin_test":             "FAIL",
            "largest_risk_asset":    None,
            "concentration_warning": False,
        }

    # --- Allocation sanity check ---
    total_allocation = sum(a.get("allocation_pct", 0) for a in assets)
    if abs(total_allocation - 100) > 0.01:   # allow tiny floating-point slack
        print(f"  ⚠️  Warning: Allocations sum to {total_allocation}%, not 100%")

    # --- Compute post-crash value (asset by asset) ---
    post_crash_value = 0.0
    for asset in assets:
        allocation_fraction    = asset.get("allocation_pct", 0) / 100
        asset_value            = total_value * allocation_fraction
        crash_fraction         = asset.get("expected_crash_pct", 0) / 100

        # Floor at zero — an asset cannot have negative value
        post_crash_asset_value = max(0.0, asset_value * (1 + crash_fraction))
        post_crash_value      += post_crash_asset_value

    # --- Runway: months of expenses covered post-crash ---
    if monthly_expenses <= 0:
        runway_months = float("inf")   # no expenses = infinite runway
    else:
        runway_months = post_crash_value / monthly_expenses

    # --- Ruin test ---
    ruin_test = "PASS" if runway_months > 12 else "FAIL"

    # --- Largest risk asset: highest (allocation% x |crash%|) ---
    def risk_impact_score(asset: Dict) -> float:
        return asset.get("allocation_pct", 0) * abs(asset.get("expected_crash_pct", 0))

    largest_risk_asset = max(assets, key=risk_impact_score).get("name") if assets else None

    # --- Concentration warning: any single asset > 40% ---
    concentration_warning = any(a.get("allocation_pct", 0) > 40 for a in assets)

    # --- Safe display rounding (preserve inf) ---
    runway_display = round(runway_months, 2) if runway_months != float("inf") else float("inf")

    return {
        "post_crash_value":      round(post_crash_value, 2),
        "runway_months":         runway_display,
        "ruin_test":             ruin_test,
        "largest_risk_asset":    largest_risk_asset,
        "concentration_warning": concentration_warning,
    }


# ============================================================
# BONUS 1 — Moderate Crash Scenario
# ============================================================

def compute_moderate_crash(portfolio: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes metrics under a moderate crash:
    each asset loses 50% of its expected crash magnitude.
    Uses deepcopy to avoid mutating the original portfolio.
    """
    moderate_portfolio = deepcopy(portfolio)
    for asset in moderate_portfolio.get("assets", []):
        asset["expected_crash_pct"] = asset.get("expected_crash_pct", 0) * 0.5
    return compute_risk_metrics(moderate_portfolio)


# ============================================================
# BONUS 2 — CLI Bar Chart (zero external libraries)
# ============================================================

def print_allocation_bar_chart(portfolio: Dict[str, Any]):
    """
    Prints a horizontal bar chart of asset allocations.
    Pure Python — no matplotlib or plotting libraries used.
    """
    assets    = portfolio.get("assets", [])
    max_width = 40   # 40 chars = 100%

    print("\n" + "=" * 58)
    print("  PORTFOLIO ALLOCATION BREAKDOWN")
    print("=" * 58)

    for asset in assets:
        name       = asset.get("name", "UNKNOWN").ljust(10)
        pct        = asset.get("allocation_pct", 0)
        bar_length = int((pct / 100) * max_width)
        bar        = "█" * bar_length
        flag       = " ⚠️ " if pct > 40 else "    "   # flag concentration risk
        print(f"  {name} | {bar:<40} {pct:>3}%{flag}")

    print("=" * 58)


# ============================================================
# DISPLAY — Both scenarios side by side
# ============================================================

def display_results(portfolio: Dict[str, Any]):
    """Runs both crash scenarios and prints results clearly."""
    total    = portfolio.get("total_value_inr", 0)
    expenses = portfolio.get("monthly_expenses_inr", 0)

    severe   = compute_risk_metrics(portfolio)
    moderate = compute_moderate_crash(portfolio)

    def ruin_icon(r):   return "✅ PASS" if r["ruin_test"] == "PASS" else "❌ FAIL"
    def conc_icon(r):   return "⚠️  YES" if r["concentration_warning"] else "✅ NO"

    print("\n" + "=" * 58)
    print("  🏦  TIMECELL PORTFOLIO RISK ANALYSIS")
    print("=" * 58)
    print(f"  Total Portfolio Value  : ₹{total:>15,.0f}")
    print(f"  Monthly Expenses       : ₹{expenses:>15,.0f}")
    print("=" * 58)

    print("\n  📉  SEVERE CRASH  (full expected crash)")
    print(f"  Post-Crash Value       : ₹{severe['post_crash_value']:>15,.2f}")
    print(f"  Runway                 :   {severe['runway_months']:>13} months")
    print(f"  Ruin Test              :  {ruin_icon(severe)}")
    print(f"  Largest Risk Asset     :  {severe['largest_risk_asset']}")
    print(f"  Concentration Warning  :  {conc_icon(severe)}")

    print("\n  📉  MODERATE CRASH  (50% of expected crash)")
    print(f"  Post-Crash Value       : ₹{moderate['post_crash_value']:>15,.2f}")
    print(f"  Runway                 :   {moderate['runway_months']:>13} months")
    print(f"  Ruin Test              :  {ruin_icon(moderate)}")
    print(f"  Largest Risk Asset     :  {moderate['largest_risk_asset']}")
    print(f"  Concentration Warning  :  {conc_icon(moderate)}")

    print_allocation_bar_chart(portfolio)


# ============================================================
# EDGE CASE TESTS
# ============================================================

def run_edge_case_tests():
    """Demonstrates robustness across edge cases."""
    print("\n\n  🧪  EDGE CASE TESTS")
    print("=" * 58)

    cases = [
        ("100% CASH — no market risk", {
            "total_value_inr": 5_000_000,
            "monthly_expenses_inr": 50_000,
            "assets": [{"name": "CASH", "allocation_pct": 100, "expected_crash_pct": 0}]
        }),
        ("80% single stock — concentration risk", {
            "total_value_inr": 1_000_000,
            "monthly_expenses_inr": 20_000,
            "assets": [
                {"name": "TSLA", "allocation_pct": 80, "expected_crash_pct": -60},
                {"name": "CASH", "allocation_pct": 20, "expected_crash_pct": 0},
            ]
        }),
        ("Empty / zero-value portfolio", {
            "total_value_inr": 0,
            "monthly_expenses_inr": 50_000,
            "assets": []
        }),
        ("Zero monthly expenses — infinite runway", {
            "total_value_inr": 2_000_000,
            "monthly_expenses_inr": 0,
            "assets": [{"name": "GOLD", "allocation_pct": 100, "expected_crash_pct": -15}]
        }),
    ]

    for label, p in cases:
        r = compute_risk_metrics(p)
        print(f"\n  Test: {label}")
        print(f"  Post-Crash: ₹{r['post_crash_value']:,.2f}  |  "
              f"Runway: {r['runway_months']} mo  |  "
              f"{r['ruin_test']}  |  "
              f"Concentration: {r['concentration_warning']}")

    print()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    portfolio = {
        "total_value_inr": 10_000_000,
        "monthly_expenses_inr": 80_000,
        "assets": [
            {"name": "BTC",     "allocation_pct": 30, "expected_crash_pct": -80},
            {"name": "NIFTY50", "allocation_pct": 40, "expected_crash_pct": -40},
            {"name": "GOLD",    "allocation_pct": 20, "expected_crash_pct": -15},
            {"name": "CASH",    "allocation_pct": 10, "expected_crash_pct":   0},
        ]
    }

    display_results(portfolio)
    run_edge_case_tests()