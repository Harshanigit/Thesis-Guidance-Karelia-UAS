"""
ask_llm.py (UPDATED VERSION — handles question variations)
──────────────────────────────────────────────────────────
WHAT THIS FILE DOES:
  1. Opens the question bank JSON file
  2. For every question group (36 total):
       - Reads the 4 variation phrasings
       - Sends EACH variation to the karelia-thesis model
       - Saves ALL 4 answers alongside the correct answer
  3. Saves everything into llm_answers.json

STRUCTURE OF OUTPUT (llm_answers.json):
  For every question group:
    - topic          : the original question topic
    - correct_answer : the one correct reference answer
    - variations     : list of 4 different question phrasings
    - llm_answers    : list of 4 LLM responses (one per variation)

HOW TO RUN:
  python3 ask_llm.py

  This produces: llm_answers.json
  Rename after each run: mv llm_answers.json llm_answers_run1.json
"""

import json
import requests
import time

# ── Settings ──────────────────────────────────────────────────────────────────
INPUT_FILE  = "karelia_thesis_questions_with_variations.json"
OUTPUT_FILE = "llm_answers.json"
MODEL_NAME  = "karelia-thesis"
OLLAMA_URL  = "http://localhost:11434/api/chat"
TIMEOUT     = 300  
# ──────────────────────────────────────────────────────────────────────────────


def ask_llm(question: str) -> str:
    """Send one question to the LLM and return the answer."""
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": question}],
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return "ERROR: Could not connect to Ollama. Make sure Ollama is running."
    except Exception as e:
        return f"ERROR: {str(e)}"


def main():
    print(f"Loading questions from: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = data.get("questions_and_answers", [])
    total_groups = sum(len(s.get("questions", [])) for s in sections)
    total_variations = total_groups * 4
    print(f"Found {len(sections)} sections")
    print(f"Found {total_groups} question groups")
    print(f"Total variations to ask: {total_variations}")
    print()

    results = []
    variation_count = 0

    for section in sections:
        section_name = section.get("section", "Unknown")
        section_result = {
            "section": section_name,
            "questions": []
        }

        for q in section.get("questions", []):
            topic          = q.get("topic", "")
            correct_answer = q.get("correct_answer", "")
            variations     = q.get("variations", [])

            llm_answers = []
            for i, variation in enumerate(variations):
                variation_count += 1
                print(f"[{variation_count}/{total_variations}] V{i+1}: {variation[:65]}...")

                llm_answer = ask_llm(variation)
                llm_answers.append(llm_answer)

                # Small pause between calls
                time.sleep(1)

            section_result["questions"].append({
                "topic":          topic,
                "correct_answer": correct_answer,
                "variations":     variations,
                "llm_answers":    llm_answers
            })

        results.append(section_result)

    # Save output
    output = {"results": results}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone! All {variation_count} answers saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
