from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# NOTE: Keep your model choice cheap and fast for dev (e.g., "gpt-4o-mini").
MODEL = "gpt-4o-mini"

def ai_reply(messages: list[dict]) -> str:
    """
    Boilerplate: calls OpenAI chat completions.
    messages: [{"role":"system"/"user"/"assistant", "content":"..."}]
    Returns: assistant text
    """
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=250,
    )
    return resp.choices[0].message.content.strip()

def build_ai_messages(question: str) -> list[dict]:
    """
    TODO (YOU WRITE THIS): Craft the system & style prompts that keep the AI from giving itself away.
    Keep this short; do not leak identity; normalize tone/length/etc.
    """
    system_prompt = (
        "You are a contestant in a text-only Q&A game. "
        "Answer succinctly and conversationally without mentioning you are an AI."
        # <- Replace with YOUR wording per assignment rules.
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
