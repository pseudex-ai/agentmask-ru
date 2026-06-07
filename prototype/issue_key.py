"""Issue an Obscura API key for a customer.

usage: python issue_key.py <customer_id> <upstream_base_url> <upstream_key>
example: python issue_key.py acme https://openrouter.ai/api/v1 sk-or-...
The customer then sets base_url=<obscura>/v1 and api_key=<printed key>.
"""

import sys

from obscura.tenants import Tenants


def main() -> None:
    if len(sys.argv) != 4:
        print("usage: python issue_key.py <customer_id> <upstream_base_url> <upstream_key>")
        return
    tenants = Tenants("tenants.db")
    key = tenants.issue(sys.argv[1], sys.argv[2], sys.argv[3])
    print("Obscura API key (give to customer):", key)


if __name__ == "__main__":
    main()
