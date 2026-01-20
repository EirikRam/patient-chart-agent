import os
from dotenv import load_dotenv

load_dotenv()

def main():
    key_ok = bool(os.getenv("OPENAI_API_KEY"))
    print("OPENAI_API_KEY present:", key_ok)
    if not key_ok:
        raise SystemExit("Missing OPENAI_API_KEY")

    # Prefer the new SDK if installed (openai>=1.x)
    try:
        from openai import OpenAI
        client = OpenAI()

        # Minimal call, low tokens, fast
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        text = resp.choices[0].message.content.strip()
        print("LLM response:", text)
        print("STATUS:", "OK" if text == "OK" else "UNEXPECTED")
        return

    except Exception as e:
        print("LLM call failed:", repr(e))
        raise

if __name__ == "__main__":
    main()
