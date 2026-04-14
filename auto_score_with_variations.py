"""
auto_score.py (UPDATED VERSION — handles question variations)
─────────────────────────────────────────────────────────────
WHAT THIS FILE DOES:
  1. Opens llm_answers.json (produced by ask_llm_with_variations.py)
  2. For every question group (36 total):
       - For EACH of the 4 variations:
           * Shows qwen2.5 the variation question
           * Shows qwen2.5 the correct answer
           * Shows qwen2.5 the LLM answer for that variation
           * Gets Accuracy score (1-3) and Completeness score (1-3)
  3. Saves all scores into auto_scored_report.txt and auto_scores.json

SCORING RUBRIC:
  ACCURACY (1-3):
    1 = Wrong or ignored Karelia rules completely
    2 = Partly followed rules but missed some
    3 = Followed ALL Karelia rules correctly

  COMPLETENESS (1-3):
    1 = Answered only a small part
    2 = Answered most but missed something
    3 = Answered everything fully

  TOTAL = Accuracy + Completeness (max 6)
    0-2 = Weak
    3-4 = Acceptable
    5-6 = Strong

HOW TO RUN:
  python3 auto_score.py llm_answers_run1.json
  python3 auto_score.py llm_answers_run2.json

WHAT GET:
  auto_scored_run1.txt   — full report for every variation
  auto_scores_run1.json  — all scores in machine-readable format
  summary_run1.txt       — quick count Strong/Acceptable/Weak
"""

import json
import requests
import time
import re
import sys

# ── Get input filename ──────────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("Usage: python3 auto_score.py llm_answers_run1.json")
    sys.exit(1)

INPUT_FILE   = sys.argv[1]
base         = INPUT_FILE.replace("llm_answers_", "").replace(".json", "")
TEXT_OUTPUT  = f"auto_scored_{base}.txt"
JSON_OUTPUT  = f"auto_scores_{base}.json"
SUMMARY_FILE = f"summary_{base}.txt"

OLLAMA_URL   = "http://localhost:11434/api/chat"
JUDGE_MODEL  = "qwen2.5"

RUBRIC_PROMPT = """You are an evaluator for a Karelia University of Applied Sciences thesis guidance chatbot.

A student asked a thesis-related question in a specific way (the variation).
The correct answer is provided as reference.
The LLM answer is what the chatbot actually said.

Score the LLM ANSWER on TWO criteria:

ACCURACY — Did the AI follow Karelia UAS rules correctly?
  1 = Wrong or ignored the rules completely
  2 = Partly followed but missed some
  3 = Followed ALL Karelia rules correctly

COMPLETENESS — Did it answer the full question?
  1 = Answered only a small part
  2 = Answered most but missed something
  3 = Answered everything fully

Respond ONLY in this exact format, nothing else:
ACCURACY: <1 or 2 or 3>
ACCURACY_REASON: <one short sentence>
COMPLETENESS: <1 or 2 or 3>
COMPLETENESS_REASON: <one short sentence>
TOTAL: <sum>
RATING: <Weak or Acceptable or Strong>
"""


def score_one(variation, correct_answer, llm_answer):
    """Send one variation+answer pair to qwen2.5 and get scores."""

    if llm_answer.startswith("ERROR"):
        return {
            "accuracy_score": 1,
            "accuracy_reason": "LLM returned an error",
            "completeness_score": 1,
            "completeness_reason": "LLM returned an error",
            "total": 2,
            "rating": "Weak"
        }

    user_message = (
        f"STUDENT QUESTION (variation): {variation}\n\n"
        f"CORRECT ANSWER:\n{correct_answer}\n\n"
        f"LLM ANSWER:\n{llm_answer}\n\n"
        f"Now score using the rubric."
    )

    payload = {
        "model": JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": RUBRIC_PROMPT},
            {"role": "user",   "content": user_message}
        ],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        raw = response.json()["message"]["content"].strip()

        def extract(label, text):
            match = re.search(rf"{label}:\s*(.+)", text, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        def safe_int(text):
            m = re.search(r'\d', text)
            return int(m.group()) if m else 1

        acc_score  = max(1, min(3, safe_int(extract("ACCURACY", raw))))
        acc_reason = extract("ACCURACY_REASON", raw) or "No reason"
        com_score  = max(1, min(3, safe_int(extract("COMPLETENESS", raw))))
        com_reason = extract("COMPLETENESS_REASON", raw) or "No reason"
        total      = acc_score + com_score
        rating     = "Strong" if total >= 5 else "Acceptable" if total >= 3 else "Weak"

        return {
            "accuracy_score":      acc_score,
            "accuracy_reason":     acc_reason,
            "completeness_score":  com_score,
            "completeness_reason": com_reason,
            "total":               total,
            "rating":              rating
        }

    except Exception as e:
        return {
            "accuracy_score": 0,
            "accuracy_reason": f"Scoring error: {str(e)}",
            "completeness_score": 0,
            "completeness_reason": "Scoring error",
            "total": 0,
            "rating": "ERROR"
        }


def main():
    print("=" * 65)
    print(f"  AUTO-SCORING: {INPUT_FILE}")
    print(f"  Judge model:  {JUDGE_MODEL}")
    print("=" * 65)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    scored_sections = []
    all_variation_scores = []   # every individual variation score
    q_number = 0
    v_number = 0
    total_sections = len(data.get("results", []))

    for s_idx, section in enumerate(data.get("results", []), 1):
        section_name = section.get("section", "Unknown")
        print(f"\nSection {s_idx}/{total_sections}: {section_name[:55]}")
        scored_questions = []

        for q in section.get("questions", []):
            q_number += 1
            topic          = q.get("topic", "")
            correct_answer = q.get("correct_answer", "")
            variations     = q.get("variations", [])
            llm_answers    = q.get("llm_answers", [])

            print(f"  Q{q_number}: {topic[:55]}")

            variation_results = []
            q_scores = []

            for i, (variation, llm_answer) in enumerate(zip(variations, llm_answers)):
                v_number += 1
                print(f"    V{i+1}: {variation[:50]}...", end=" ", flush=True)

                scores = score_one(variation, correct_answer, llm_answer)
                icons  = {"Strong": "✅", "Acceptable": "⚠️ ", "Weak": "❌", "ERROR": "⛔"}
                print(f"{icons.get(scores['rating'], '?')} {scores['rating']} ({scores['total']}/6)")

                variation_results.append({
                    "variation_number": i + 1,
                    "variation":        variation,
                    "llm_answer":       llm_answer,
                    "accuracy_score":   scores["accuracy_score"],
                    "accuracy_reason":  scores["accuracy_reason"],
                    "completeness_score": scores["completeness_score"],
                    "completeness_reason": scores["completeness_reason"],
                    "total":            scores["total"],
                    "rating":           scores["rating"]
                })
                q_scores.append(scores)
                all_variation_scores.append(scores)
                time.sleep(0.5)

            # Calculate average score for this question group
            valid_q = [s for s in q_scores if s["rating"] != "ERROR"]
            avg_q = round(sum(s["total"] for s in valid_q) / len(valid_q), 2) if valid_q else 0
            ratings = [s["rating"] for s in q_scores]

            scored_questions.append({
                "topic":            topic,
                "correct_answer":   correct_answer,
                "average_score":    avg_q,
                "variation_ratings": ratings,
                "variations":       variation_results
            })

        scored_sections.append({
            "section":   section_name,
            "questions": scored_questions
        })

    # ── Overall statistics ─────────────────────────────────────────────────────
    valid_all = [s for s in all_variation_scores if s["rating"] != "ERROR"]
    total_v   = len(all_variation_scores)
    n_strong  = sum(1 for s in valid_all if s["rating"] == "Strong")
    n_accept  = sum(1 for s in valid_all if s["rating"] == "Acceptable")
    n_weak    = sum(1 for s in valid_all if s["rating"] == "Weak")
    n_error   = sum(1 for s in all_variation_scores if s["rating"] == "ERROR")
    avg_all   = round(sum(s["total"] for s in valid_all) / len(valid_all), 2) if valid_all else 0

    # ── Statistics per variation number (V1, V2, V3, V4) ─────────────────────
    variation_stats = {}
    for v_idx in range(4):
        v_scores = []
        for section in scored_sections:
            for q in section["questions"]:
                if v_idx < len(q["variations"]):
                    v_scores.append(q["variations"][v_idx])
        valid_v = [s for s in v_scores if s["rating"] != "ERROR"]
        variation_stats[f"V{v_idx+1}"] = {
            "strong":     sum(1 for s in valid_v if s["rating"] == "Strong"),
            "acceptable": sum(1 for s in valid_v if s["rating"] == "Acceptable"),
            "weak":       sum(1 for s in valid_v if s["rating"] == "Weak"),
            "average":    round(sum(s["total"] for s in valid_v) / len(valid_v), 2) if valid_v else 0
        }

    # ── Save JSON ──────────────────────────────────────────────────────────────
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({
            "input_file": INPUT_FILE,
            "summary": {
                "total_variations": total_v,
                "strong":    n_strong,
                "acceptable": n_accept,
                "weak":      n_weak,
                "errors":    n_error,
                "average_score": avg_all,
                "per_variation": variation_stats
            },
            "results": scored_sections
        }, f, indent=2, ensure_ascii=False)

    # ── Save text report ───────────────────────────────────────────────────────
    lines = []
    lines.append("=" * 72)
    lines.append(f"  AUTO-SCORED REPORT — {INPUT_FILE}")
    lines.append(f"  Scored by: {JUDGE_MODEL} (local Ollama)")
    lines.append("=" * 72)

    q_num = 0
    for section in scored_sections:
        lines.append(f"\n{'=' * 72}")
        lines.append(f"  SECTION: {section['section']}")
        lines.append(f"{'=' * 72}")

        for q in section["questions"]:
            q_num += 1
            lines.append(f"\nQ{q_num}. TOPIC: {q['topic']}")
            lines.append(f"  Average score across all variations: {q['average_score']}/6")
            lines.append(f"  Ratings per variation: {' | '.join(q['variation_ratings'])}")
            lines.append("─" * 72)
            lines.append(f"  CORRECT ANSWER:")
            lines.append("  " + q["correct_answer"].replace("\n", "\n  "))
            lines.append("")

            for vr in q["variations"]:
                icon = {"Strong": "✅", "Acceptable": "⚠️ ", "Weak": "❌", "ERROR": "⛔"}.get(vr["rating"], "?")
                lines.append(f"  ── VARIATION {vr['variation_number']} ──────────────────────────────────────")
                lines.append(f"  Student asked: {vr['variation']}")
                lines.append(f"  {icon} {vr['rating'].upper()}  |  Total: {vr['total']}/6")
                lines.append(f"  Accuracy     : {vr['accuracy_score']}/3 — {vr['accuracy_reason']}")
                lines.append(f"  Completeness : {vr['completeness_score']}/3 — {vr['completeness_reason']}")
                lines.append(f"  LLM Answer   : {vr['llm_answer'][:200]}...")
                lines.append("")
            lines.append("  YOUR OVERRIDE (if you disagree with any variation score):")
            lines.append("  V1[ ] V2[ ] V3[ ] V4[ ]  Notes: ")

    # ── Summary ────────────────────────────────────────────────────────────────
    lines.append("\n" + "=" * 72)
    lines.append("  FINAL SUMMARY — ALL VARIATIONS")
    lines.append("=" * 72)
    lines.append(f"  Input file:              {INPUT_FILE}")
    lines.append(f"  Total variations scored: {total_v}")
    lines.append(f"  Strong   (5-6 pts):      {n_strong}  ({n_strong/total_v:.0%})")
    lines.append(f"  Acceptable (3-4 pts):    {n_accept}  ({n_accept/total_v:.0%})")
    lines.append(f"  Weak     (0-2 pts):      {n_weak}  ({n_weak/total_v:.0%})")
    lines.append(f"  Errors:                  {n_error}")
    lines.append(f"  Average score:           {avg_all} / 6")
    lines.append("")
    lines.append("  ── SCORES BY VARIATION TYPE ──────────────────────────────")
    lines.append(f"  {'':6} {'Strong':>8} {'Acceptable':>12} {'Weak':>6} {'Average':>9}")
    lines.append("  " + "─" * 50)
    for vkey, vstats in variation_stats.items():
        n = 36  # 36 questions per variation
        lines.append(
            f"  {vkey:6} {vstats['strong']:>5} ({vstats['strong']/n:.0%})  "
            f"{vstats['acceptable']:>5} ({vstats['acceptable']/n:.0%})  "
            f"{vstats['weak']:>3} ({vstats['weak']/n:.0%})  "
            f"{vstats['average']:>6}/6"
        )
    lines.append("")
    lines.append("  NOTE: V1 = formal phrasing, V4 = very casual phrasing")
    lines.append("  Compare V1 vs V4 to see if question phrasing affects quality.")
    lines.append("")
    lines.append("  NOTE: Review and override any scores you disagree with.")
    lines.append("  You are responsible for the final numbers.")
    lines.append("=" * 72)

    with open(TEXT_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── Summary file ───────────────────────────────────────────────────────────
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(f"""{'=' * 55}
  SUMMARY — {INPUT_FILE}
{'=' * 55}
  Total variations:   {total_v}
  Strong (5-6 pts):   {n_strong} / {total_v}  ({n_strong/total_v:.0%})
  Acceptable (3-4):   {n_accept} / {total_v}  ({n_accept/total_v:.0%})
  Weak (0-2 pts):     {n_weak} / {total_v}  ({n_weak/total_v:.0%})
  Average score:      {avg_all} / 6

  SCORES BY VARIATION TYPE:
  V1 (formal):     Strong {variation_stats['V1']['strong']}/36  Avg {variation_stats['V1']['average']}/6
  V2 (semi-formal):Strong {variation_stats['V2']['strong']}/36  Avg {variation_stats['V2']['average']}/6
  V3 (casual):     Strong {variation_stats['V3']['strong']}/36  Avg {variation_stats['V3']['average']}/6
  V4 (very casual):Strong {variation_stats['V4']['strong']}/36  Avg {variation_stats['V4']['average']}/6
{'=' * 55}""")

    # ── Print to screen ────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  AUTO-SCORING COMPLETE")
    print("=" * 65)
    print(f"  Total variations: {total_v}")
    print(f"  Strong:     {n_strong}/{total_v}  ({n_strong/total_v:.0%})")
    print(f"  Acceptable: {n_accept}/{total_v}  ({n_accept/total_v:.0%})")
    print(f"  Weak:       {n_weak}/{total_v}  ({n_weak/total_v:.0%})")
    print(f"  Average:    {avg_all} / 6")
    print()
    print("  SCORES BY VARIATION TYPE:")
    for vkey, vstats in variation_stats.items():
        print(f"    {vkey}: Strong {vstats['strong']}/36  Avg {vstats['average']}/6")
    print()
    print(f"  Files saved:")
    print(f"    {TEXT_OUTPUT}")
    print(f"    {JSON_OUTPUT}")
    print(f"    {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
