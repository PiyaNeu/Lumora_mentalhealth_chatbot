"""Khalti ePayment v2 (sandbox by default): initiate + lookup.

Docs: https://docs.khalti.com/khalti-epayment/  — amounts are in paisa.
A booking is marked paid only after `lookup` returns status "Completed".
"""
import requests
from flask import current_app


class KhaltiError(RuntimeError):
    pass


def is_configured():
    return bool(current_app.config.get("KHALTI_SECRET_KEY"))


def _post(path, payload):
    cfg = current_app.config
    try:
        resp = requests.post(f"{cfg['KHALTI_BASE_URL']}{path}", json=payload, timeout=15,
                             headers={"Authorization": f"Key {cfg['KHALTI_SECRET_KEY']}"})
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise KhaltiError(f"Could not reach Khalti: {exc}") from exc
    if resp.status_code >= 400:
        raise KhaltiError(f"Khalti returned {resp.status_code}: {data}")
    return data


def initiate(amount_npr, order_id, order_name, return_url, website_url, customer=None):
    """Start a payment. Returns (pidx, payment_url)."""
    payload = {
        "return_url": return_url,
        "website_url": website_url,
        "amount": int(amount_npr) * 100,
        "purchase_order_id": order_id,
        "purchase_order_name": order_name,
    }
    if customer:
        payload["customer_info"] = customer
    data = _post("/epayment/initiate/", payload)
    if "pidx" not in data or "payment_url" not in data:
        raise KhaltiError(f"Unexpected Khalti response: {data}")
    return data["pidx"], data["payment_url"]


def lookup(pidx):
    """Return Khalti's record for a payment (status, transaction_id, total_amount, ...)."""
    return _post("/epayment/lookup/", {"pidx": pidx})
