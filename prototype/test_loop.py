"""Self-contained proof of the tokenization loop — no LLM, no pip, stdlib only.

Proves the two load-bearing properties:
  1. Real PII never appears in what is sent to the model (masked request).
  2. A token echoed back inside a tool_call argument detokenizes to the real
     value, so the client's tool executes on real data.
"""

import json
import re

from veilgate.detect import detect_pii
from veilgate.redact import mask_text, unmask_text
from veilgate.vault import Vault


def main() -> None:
    vault = Vault(":memory:", "test")

    real_phone = "+7 999 123-45-67"
    real_email = "ivan@mail.ru"
    user_message = f"Найди заказ по телефону {real_phone} и почте {real_email}"

    # 1. Outbound: real -> token (what the model actually receives)
    masked = mask_text(user_message, vault, detect_pii(user_message))
    print("SENT TO MODEL:", masked)
    assert real_phone not in masked, "LEAK: real phone reached the model"
    assert real_email not in masked, "LEAK: real email reached the model"

    # Recover the tokens the model saw (idempotent — same tokens as in `masked`)
    tokens = {span.entity_type: vault.tokenize(span.value, span.entity_type)
              for span in detect_pii(user_message)}

    # 2. The model emits a tool call echoing the tokens it was given
    model_tool_args = json.dumps({"phone": tokens["PHONE"], "email": tokens["EMAIL"]})
    print("MODEL TOOL CALL (tokens):", model_tool_args)

    # 3. Inbound: token -> real, so the client's tool runs on real values
    real_tool_args = unmask_text(model_tool_args, vault)
    print("TOOL EXECUTES WITH:", real_tool_args)
    digits = lambda s: re.sub(r"\D", "", s)  # vault returns canonical (normalized) phone
    assert digits(real_phone) in digits(real_tool_args), "tool did not receive the real phone"
    assert real_email in real_tool_args, "tool did not receive the real email"
    assert tokens["PHONE"] not in real_tool_args, "token leaked into tool args"

    print("\nPASS — model saw only tokens; tool received real values.")


if __name__ == "__main__":
    main()
