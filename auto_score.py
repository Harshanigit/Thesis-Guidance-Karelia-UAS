"""
auto_score.py
─────────────
Uses a local Ollama model as an automatic judge to score
each LLM answer using the THREE-LEVEL SCORING SCALE.
No API key needed — uses your local Ollama server.
"""

import json
import requests
import time
import re

INPUT_FILE    = "llm_answers.json"
TEXT_OUTPUT   = "auto_scored_report.txt"
JSON_OUTPUT   = "auto_scores.json"
SUMMARY_FILE  = "auto_scores_summary.txt"
OLLAMA_URL    = "http://localhost:11434/api/chat"
JUDGE_MODEL   = "qwen2.5"

RUBRIC_PROMPT = """You are an evaluator for a Karelia University of Applied Sciences thesis guidance chatbot.

Score the LLM ANSWER on TWO criteria:

ACCURACY — Did the AI follow Karelia UAS rules correctly?
  1 = Wrong or ignored the rules completely
  2 = Partly followed but missed some
  3 = Followed ALL Karelia rules correctly

COMPLETENESS — Did it answer the full question?
  1 = Answered only a small part
  2 = Answered most but missed something
  3 = Answered everything fully

Respond ONLY in this exact format:
ACCURACY: <1 or 2 or 3>
ACCURACY_REASON: <one short sentence>
COMPLETENESS: <1 or 2 or 3>
COMPLETENESS_REASON: <one short sentence>
TOTAL: <sum>
RATING: <Weak or Acceptable or Strong>
"""


def score_one(question, correct_answer, llm_answer):
    if llm_answer.startswith("ERROR"):
        return {"accuracy_score":1,"accuracy_reason":"LLM returned an error","completeness_score":1,"completeness_reason":"LLM returned an error","total":2,"rating":"Weak"}

    user_message = f"QUESTION: {question}\n\nCORRECT ANSWER:\n{correct_answer}\n\nLLM ANSWER:\n{llm_answer}\n\nNow score."

    payload = {"model": JUDGE_MODEL, "messages": [{"role":"system","content":RUBRIC_PROMPT},{"role":"user","content":user_message}], "stream": False}

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        raw = response.json()["message"]["content"].strip()

        def extract(label, text):
            match = re.search(rf"{label}:\s*(.+)", text, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        acc_score  = max(1, min(3, int(re.search(r'\d', extract("ACCURACY", raw)).group()))) if re.search(r'\d', extract("ACCURACY", raw)) else 1
        acc_reason = extract("ACCURACY_REASON", raw) or "No reason"
        com_score  = max(1, min(3, int(re.search(r'\d', extract("COMPLETENESS", raw)).group()))) if re.search(r'\d', extract("COMPLETENESS", raw)) else 1
        com_reason = extract("COMPLETENESS_REASON", raw) or "No reason"
        total      = acc_score + com_score
        rating     = "Strong" if total >= 5 else "Acceptable" if total >= 3 else "Weak"

        return {"accuracy_score":acc_score,"accuracy_reason":acc_reason,"completeness_score":com_score,"completeness_reason":com_reason,"total":total,"rating":rating}

    except Exception as e:
        return {"accuracy_score":0,"accuracy_reason":f"Error: {e}","completeness_score":0,"completeness_reason":"Error","total":0,"rating":"ERROR"}


def main():
    print("Loading:", INPUT_FILE)
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    scored_sections = []
    all_scores = []
    q_number = 0
    total_sections = len(data.get("results", []))

    for s_idx, section in enumerate(data.get("results", []), 1):
        section_name = section.get("section", "Unknown")
        print(f"\nSection {s_idx}/{total_sections}: {section_name[:55]}")
        scored_vars = []

        for var in section.get("variations", []):
            q_number += 1
            question       = var.get("question", "")
            correct_answer = var.get("correct_answer", "")
            llm_answer     = var.get("llm_answer", "")

            print(f"  Q{q_number}/36: {question[:55]}...", end=" ", flush=True)
            scores = score_one(question, correct_answer, llm_answer)
            icons  = {"Strong":"✅","Acceptable":"⚠️","Weak":"❌","ERROR":"⛔"}
            print(f"{icons.get(scores['rating'],'?')} {scores['rating']} ({scores['total']}/6)")

            scored_vars.append({**var, **scores})
            all_scores.append(scores)
            time.sleep(0.5)

        scored_sections.append({"section": section_name, "variations": scored_vars})

    valid    = [s for s in all_scores if s["rating"] != "ERROR"]
    total_q  = len(all_scores)
    n_strong = sum(1 for s in valid if s["rating"] == "Strong")
    n_accept = sum(1 for s in valid if s["rating"] == "Acceptable")
    n_weak   = sum(1 for s in valid if s["rating"] == "Weak")
    n_error  = sum(1 for s in all_scores if s["rating"] == "ERROR")
    avg      = round(sum(s["total"] for s in valid) / len(valid), 2) if valid else 0

    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"summary":{"total":total_q,"strong":n_strong,"acceptable":n_accept,"weak":n_weak,"errors":n_error,"average":avg},"results":scored_sections}, f, indent=2, ensure_ascii=False)

    lines = []
    lines.append("=" * 72)
    lines.append("  AUTO-SCORED REPORT — Karelia UAS Thesis Guidance Assistant")
    lines.append(f"  Scored by: {JUDGE_MODEL} (local Ollama)")
    lines.append("=" * 72)

    q_num = 0
    for section in scored_sections:
        lines.append(f"\n{'=' * 72}")
        lines.append(f"  SECTION: {section['section']}")
        lines.append(f"{'=' * 72}")
        for var in section["variations"]:
            q_num += 1
            icon = {"Strong":"✅","Acceptable":"⚠️ ","Weak":"❌","ERROR":"⛔"}.get(var["rating"],"?")
            lines.append(f"\nQ{q_num}. {var['question']}")
            lines.append("─" * 72)
            lines.append(f"  {icon} AUTO RATING: {var['rating'].upper()}  |  Total: {var['total']}/6")
            lines.append(f"  Accuracy     : {var['accuracy_score']}/3 — {var['accuracy_reason']}")
            lines.append(f"  Completeness : {var['completeness_score']}/3 — {var['completeness_reason']}")
            lines.append("")
            lines.append("  CORRECT ANSWER:")
            lines.append("  " + var["correct_answer"].replace("\n", "\n  "))
            lines.append("")
            lines.append("  LLM ANSWER:")
            lines.append("  " + var["llm_answer"].replace("\n", "\n  "))
            lines.append("")
            lines.append("  YOUR OVERRIDE (if you disagree):")
            lines.append("  Accuracy [ ]  Completeness [ ]  Total [ ]  Rating [              ]")
            lines.append("  Notes: ")

    lines.append("\n" + "=" * 72)
    lines.append("  FINAL SUMMARY")
    lines.append("=" * 72)
    lines.append(f"  Total questions:       {total_q}")
    lines.append(f"  Strong   (5-6 pts):    {n_strong}  ({n_strong/total_q:.0%})")
    lines.append(f"  Acceptable (3-4 pts):  {n_accept}  ({n_accept/total_q:.0%})")
    lines.append(f"  Weak     (0-2 pts):    {n_weak}  ({n_weak/total_q:.0%})")
    lines.append(f"  Errors:                {n_error}")
    lines.append(f"  Average score:         {avg} / 6")
    lines.append("")
    lines.append("  NOTE: Review and override scores you disagree with.")
    lines.append("  You are responsible for the final numbers.")
    lines.append("=" * 72)

    with open(TEXT_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    summary = f"""{'=' * 50}
  SCORING SUMMARY — Karelia Thesis Assistant
{'=' * 50}
  Total questions:    {total_q}
  Strong (5-6 pts):   {n_strong} / {total_q}  ({n_strong/total_q:.0%})
  Acceptable (3-4):   {n_accept} / {total_q}  ({n_accept/total_q:.0%})
  Weak (0-2 pts):     {n_weak} / {total_q}  ({n_weak/total_q:.0%})
  Errors:             {n_error}
  Average score:      {avg} / 6
{'=' * 50}"""

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary)

    print("\n" + "=" * 60)
    print("  AUTO-SCORING COMPLETE")
    print("=" * 60)
    print(f"  Strong:     {n_strong}/{total_q}  ({n_strong/total_q:.0%})")
    print(f"  Acceptable: {n_accept}/{total_q}  ({n_accept/total_q:.0%})")
    print(f"  Weak:       {n_weak}/{total_q}  ({n_weak/total_q:.0%})")
    print(f"  Avg score:  {avg} / 6")
    print(f"\n  Files saved:")
    print(f"    {TEXT_OUTPUT}")
    print(f"    {JSON_OUTPUT}")
    print(f"    {SUMMARY_FILE}")

if __name__ == "__main__":
    main()
