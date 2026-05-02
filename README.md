# timecell-intern-[Dhruvi-202301401]

---

## Setup

```bash
pip install google-generativeai python-dotenv yfinance requests
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your-key-here
```

Get a free Gemini key at: https://aistudio.google.com

---

---

```markdown
## Loom Video
https://www.loom.com/share/2a7c02184bc44a51957daec086815554
## Run Instructions

```bash
python task1.py
python task2.py
python task3.py
python task4.py

## Task 1 — Portfolio Risk Calculator

**File:** `task1.py`  
**Run:** `python task1.py`

### Approach

The core function `compute_risk_metrics()` computes five metrics from a portfolio dict. Key decisions:

- **Floor at zero**: an asset cannot have negative value after a crash, so `max(0.0, asset_value * (1 + crash_fraction))` prevents unrealistic results.
- **Infinite runway**: when monthly expenses are zero, runway is `float("inf")` — mathematically correct and handled cleanly in display.
- **Allocation sanity check**: if allocations don't sum to ~100%, the user gets a warning rather than a silent wrong answer.
- **Risk impact score**: `allocation% × |crash%|` is used to find the largest risk asset — this correctly weights both size and volatility, not just one.

### Bonus

- **Moderate crash scenario**: uses `deepcopy` to avoid mutating the original portfolio, then halves all crash magnitudes.
- **CLI bar chart**: pure Python with Unicode block characters — no matplotlib, no external libraries.

### AI Usage

Claude was used to identify edge cases (zero expenses, empty asset list, allocations not summing to 100%) and suggest the `deepcopy` pattern for the moderate scenario. All logic and math written and verified manually.

### Edge Cases Handled

| Case | Behaviour |
|---|---|
| Empty asset list | Returns zero metrics, no crash |
| Zero total value | Returns zero metrics safely |
| Zero monthly expenses | Runway = `inf` (no ruin possible) |
| Allocations ≠ 100% | Prints warning, continues |
| Single asset > 40% | `concentration_warning = True` |

---

## Task 2 — Live Market Data Fetch

**File:** `task2.py`  
**Run:** `python task2.py`

### Approach

Three assets fetched from two free APIs:

| Asset | Source | Conversion |
|---|---|---|
| NIFTY 50 | Yahoo Finance (`yfinance`) | Direct INR |
| BTC | CoinGecko public API | Direct USD |
| GOLD | Yahoo Finance (GC=F futures × USDINR=X) | USD/oz → INR/g |

Gold conversion formula:  
`INR per gram = (gold_usd_per_troy_oz × usd_to_inr) ÷ 31.1035`

### Error Handling

- Each fetcher is isolated — one failure does not crash the others.
- `with_retry()` wraps every fetch with configurable retries and delay.
- Yahoo Finance `fast_info` can return `None` for closed markets, so a fallback to `history(period="1d")` is used.
- Table only renders if at least one fetch succeeds.

### AI Usage

Claude helped structure the retry wrapper as a reusable higher-order function rather than copy-pasting try/except blocks. IST timezone offset and the gold unit conversion formula were verified with Claude.

---

## Task 3 — AI-Powered Portfolio Explainer

**File:** `task3.py`  
**Run:** `python task3.py`

### API Used

**Google Gemini** (`gemini-2.5-flash` via `google-generativeai`)

Gemini was chosen because its free tier requires no credit card and provides enough quota for this assessment. The prompt engineering principles are identical regardless of provider — the prompts would work unchanged with Claude or GPT-4o.

### Prompt Engineering Approach

**What I tried first:** A single prompt with all instructions inline. Problem: the model sometimes returned prose instead of JSON, and sometimes invented numbers.

**What I changed:**

1. **Separated system and user messages.** The system prompt defines role, tone, and output format. The user message contains only data. This prevents format instructions from being buried under numbers.

2. **Pre-computed all metrics in the user message.** Instead of asking the model to calculate post-crash value, runway, and risk scores, I compute them in Python and pass the results directly. This eliminates the main source of numeric errors in LLM financial analysis.

3. **Explicit JSON template in the system prompt.** Showing the exact structure with placeholder text produces far more consistent output than saying "respond in JSON".

4. **Tone levels as prompt variants.** Rather than one generic prompt, the system prompt swaps in a tone-specific instruction block. This lets the same pipeline serve beginners and expert CIOs without separate codebases.

5. **Defensive parser.** Gemini sometimes wraps JSON in markdown fences even when told not to. The parser strips these aggressively with regex before `json.loads()`.

### Bonus Features

- **Configurable tone**: `'beginner'`, `'experienced'`, or `'expert'` — adjusts language complexity in the system prompt.
- **Critic-actor architecture**: a second independent LLM call fact-checks the first for mathematical accuracy and logical consistency. This is a real production technique used in AI pipelines to reduce hallucination.
- **Rate limit back-off**: exponential wait (35s, 65s) between retries to handle Gemini's per-minute free-tier quota automatically.
- **Mock fallback**: if no API key is set, a realistic mock response is returned so the script always demonstrates its full structure.

### AI Usage

Claude was used as a coding assistant for the retry logic, JSON parsing defensive patterns, and the critic-actor architecture concept. All prompt text was written and iterated manually.

---

## Task 4 — Portfolio Health Score

**File:** `task4.py`  
**Run:** `python task4.py`

### What I Built

A **0–100 Portfolio Health Score** — like a CIBIL credit score but for investment portfolios. Four transparent, equally-weighted components (25 points each) collapse the raw risk metrics into a single number with a letter grade.

### Why I Built This

Timecell surfaces metrics like crash survival, runway months, and concentration warnings. But non-expert clients still ask: *"Is my portfolio OK or not?"* A single score answers that instantly. It also creates a natural engagement loop — users want to improve their score, which drives continued use of the platform.

### Scoring Formula

| Component | Max | Logic |
|---|---|---|
| **Runway Score** | 25 | Logarithmic curve: 6 mo → 0, 12 mo → ~12, 60+ mo → 25 |
| **Crash Survival** | 25 | Linear: post-crash value as % of total × 25 |
| **Diversification** | 25 | Inverted Herfindahl-Hirschman Index (HHI) |
| **Ruin Test** | 25 | Binary: 25 if PASS, 0 if FAIL |

**Why logarithmic for runway?** Going from 3 months to 6 months runway matters far more to a real family than going from 60 to 63. A log curve reflects this diminishing return correctly.

**Why HHI for diversification?** HHI (sum of squared allocation fractions) is the standard academic measure of market concentration — the same formula used by regulators to assess industry monopoly risk. Applied to portfolios, it correctly penalises both single-asset concentration and any uneven weighting.

### Grade Scale

| Score | Grade | Label |
|---|---|---|
| 90–100 | A+ | Fortress |
| 75–89 | A | Strong |
| 60–74 | B | Moderate |
| 45–59 | C | Caution |
| 0–44 | D | Danger |

### Features

- Full score report with visual bar for each component
- Actionable tip identifying the single weakest area
- Side-by-side portfolio comparison (useful for before/after rebalancing)
- Standalone module — no imports from other tasks required

### AI Usage

Claude helped calibrate the logarithmic scoring curve anchors and suggested the HHI formula for diversification scoring. The grade scale and tip text were designed manually to match Timecell's wealth-management context.

---

## What Was Hardest

**Task 3 — prompt reliability.** Getting the LLM to return clean JSON every time without markdown fences, invented numbers, or the wrong verdict took several iterations. The fix was separating format instructions (system prompt) from data (user message) and pre-computing all metrics in Python so the model never had to do arithmetic. The defensive regex parser was added after observing that Gemini adds code fences even when explicitly told not to.

---

## Repository Structure

```
timecell-intern-[your-name]/
├── task1.py          # Portfolio Risk Calculator
├── task2.py          # Live Market Data Fetch
├── task3.py          # AI-Powered Portfolio Explainer
├── task4.py          # Portfolio Health Score
├── .env              # API keys (not committed)
├── .gitignore        # Excludes .env
└── README.md
```
