"""
ask_llm.py
----------
Reads questions from your JSON file, sends each one to the LLM,
and saves all the LLM's answers into a new file called llm_answers.json
"""

import json
import requests
import time

# ── Settings ──────────────────────────────────────────────────────────────────
INPUT_FILE  = "karelia_thesis_guidance_questions_and_answers.json"  
OUTPUT_FILE = "llm_answers.json"    
MODEL_NAME  = "karelia-thesis"      
OLLAMA_URL  = "http://localhost:11434/api/chat"  
# ──────────────────────────────────────────────────────────────────────────────


def ask_llm(question: str) -> str:
    """Send one question to Ollama and return the answer as a string."""
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": question}],
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return "ERROR: Could not connect to Ollama. Make sure Ollama is running."
    except Exception as e:
        return f"ERROR: {str(e)}"


def main():
    # Load the original questions file
    print(f"Loading questions from: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        original_data = json.load(f)

    results = []
    sections = original_data.get("questions_and_answers", [])
    total_questions = sum(len(s.get("variations", [])) for s in sections)

    print(f"Found {len(sections)} sections with {total_questions} total questions.\n")

    question_count = 0
    for section in sections:
        section_name = section.get("section", "Unknown section")
        section_result = {
            "section": section_name,
            "variations": []
        }

        for variation in section.get("variations", []):
            question_count += 1
            question  = variation.get("question", "")
            correct_answer = variation.get("answer", "")

            print(f"[{question_count}/{total_questions}] Asking: {question[:70]}...")

            llm_answer = ask_llm(question)

            section_result["variations"].append({
                "question":       question,
                "correct_answer": correct_answer,
                "llm_answer":     llm_answer
            })

            # Small pause to avoid overwhelming the local model
            time.sleep(1)

        results.append(section_result)

    # Save all results to the output file
    output = {"results": results}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone! All answers saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
