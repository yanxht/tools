from openai import OpenAI
import json
import re


def process_text(text: str, instruction_file: str, api_key: str) -> str:
    """Apply instructions from a file to transform text via DeepSeek."""
    with open(instruction_file, "r", encoding="utf-8") as f:
        instructions = f.read()

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
    )

    return response.choices[0].message.content.strip()


def infer_speakers(text: str, api_key: str) -> dict:
    """
    Ask DeepSeek to identify speakers in the text and label dialogue lines.
    Returns:
        {
            "speakers": [
                {"id": "Speaker 1", "gender": "Female", "description": "narrator"},
                {"id": "Speaker 2", "gender": "Male", "description": "the doctor"},
            ],
            "labeled_text": "The full text with [Speaker 1]: / [Speaker 2]: labels"
        }
    """
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    prompt = """Analyze the following text and identify all distinct speakers/narrators.

Your tasks:
1. Identify each distinct speaker. Assign them labels: Speaker 1, Speaker 2, etc.
2. Infer each speaker's gender (Male, Female, or Unknown).
3. Rewrite the text with inline speaker labels: [Speaker 1]: text here

Rules:
- If there is only one narrator, label everything as [Speaker 1].
- Preserve the original text exactly — do not rephrase, summarize, or omit anything.
- Dialogue markers like "he said" / "she asked" help you infer speakers.
- Return ONLY a JSON object with keys: "speakers" (array of {id, gender, description}) and "labeled_text" (string).

Text:
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a precise text analysis expert. Output ONLY valid JSON."},
            {"role": "user", "content": prompt + text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown wrappers
    json_str = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Rescue: try sanitizing newlines
        sanitized = json_str.replace("\n", "\\n")
        sanitized = sanitized.replace("{\\n", "{").replace("\\n}", "}")
        try:
            return json.loads(sanitized)
        except Exception:
            # Fallback: treat entire text as single speaker
            print("⚠️ Speaker inference failed, falling back to single speaker.")
            return {
                "speakers": [{"id": "Speaker 1", "gender": "Unknown", "description": "narrator"}],
                "labeled_text": f"[Speaker 1]: {text}",
            }
