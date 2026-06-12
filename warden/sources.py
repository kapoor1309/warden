"""The company's authoritative systems of record.

Warden does NOT trust what an agent claims about an invoice. It re-reads the
real records here and compares. That is the whole trick: a hijacked agent can
lie about where a bank account "came from", but it cannot change what is
actually written in the vendor master.
"""

import json
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "sources"


class Sources:
    def __init__(self, vendor_master: dict, purchase_orders: dict, policy: dict):
        self.vendor_master = vendor_master
        self.purchase_orders = purchase_orders
        self.policy = policy

    @classmethod
    def from_dir(cls, path=DEFAULT_DIR):
        path = Path(path)
        return cls(
            vendor_master=json.loads((path / "vendor_master.json").read_text()),
            purchase_orders=json.loads((path / "purchase_orders.json").read_text()),
            policy=json.loads((path / "policy.json").read_text()),
        )

    def vendor_account(self, vendor_id):
        """The ONLY account this vendor is allowed to be paid at. None if unknown."""
        vendor = self.vendor_master.get(vendor_id)
        return vendor.get("account_on_file") if vendor else None

    def purchase_order(self, invoice_id):
        """The purchase order this invoice must match. None if there is no PO."""
        return self.purchase_orders.get(invoice_id)

    @property
    def spend_limit(self):
        return self.policy.get("spend_limit")

    @property
    def required_order(self):
        return self.policy.get("required_order", [])
