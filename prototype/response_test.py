"""Prove the response leg: the user must see the REAL phone, not the token,
even though the model only ever saw the fake one.
"""

from openai import OpenAI

client = OpenAI(base_url="http://localhost:4000/v1", api_key="veilgate-dev")
MODEL = "openai/gpt-4.1-mini"

REAL = "+7 999 123-45-67"
message = (
    f"Запишите меня на визит, мой телефон {REAL}. "
    "В ответе обязательно повтори мой номер телефона дословно, чтобы я проверил."
)


def main() -> None:
    response = client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": message}]
    )
    content = response.choices[0].message.content or ""
    print("REAL phone:", REAL)
    print("USER SEES :", content.replace("\n", " "))
    print("REAL in user-facing reply:", REAL in content)


if __name__ == "__main__":
    main()
