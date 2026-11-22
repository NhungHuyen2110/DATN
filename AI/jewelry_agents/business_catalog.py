"""Read-only authoritative product snapshot from the existing Business API."""
import os
import requests
from decimal import Decimal
from shared.observability import correlation_headers


class CatalogUnavailable(RuntimeError):
    pass


def fetch_shipping_policy():
    base = os.getenv('BUSINESS_API_URL', 'http://127.0.0.1:8001').rstrip('/')
    try:
        response = requests.get(base + '/checkout/payment-methods', timeout=3, headers=correlation_headers())
        response.raise_for_status()
        values = response.json()['shipping']
        policy = {key: Decimal(str(values[key])) for key in ('flat_fee_vnd', 'free_from_vnd')}
        if any(not value.is_finite() or value < 0 for value in policy.values()):
            raise ValueError('Invalid policy amounts')
        return policy
    except (requests.RequestException, ValueError, ArithmeticError, TypeError, KeyError):
        raise CatalogUnavailable('Current shipping policy unavailable') from None


def fetch_catalog():
    base = os.getenv("BUSINESS_API_URL", "http://127.0.0.1:8001").rstrip("/")
    products = {}
    try:
        with requests.Session() as client:
            for page in range(1, 51):
                response = client.get(base + "/products", params={"page": page, "page_size": 100}, timeout=3,
                                      headers=correlation_headers())
                response.raise_for_status()
                payload = response.json()
                items, total = payload["items"], payload["total"]
                if type(total) is not int or total < 0 or not isinstance(items, list):
                    raise ValueError("invalid catalog page")
                for item in items:
                    pid = item["id"]
                    if type(pid) is not int or pid in products:
                        raise ValueError("invalid or duplicate product identity")
                    products[pid] = {
                        "ProductID": pid, "ProductName": item["name"], "SKU": item["sku"],
                        "Price": item["price_vnd"], "Stock": item["stock"],
                        "Category": item["category"]["name"], "CategoryID": item["category"]["id"],
                        "Brand": item["brand"]["name"], "Material": item["material"]["name"],
                        "MaterialID": item["material"]["id"],
                        "Gemstone": item["gemstone"]["name"], "GemstoneID": item["gemstone"]["id"],
                        "Collection": item["collection"]["name"],
                        "verified_source": "business_api",
                    }
                if len(products) == total:
                    return products
                if not items or len(products) > total:
                    raise ValueError("catalog pagination changed; retry query")
        raise ValueError("catalog exceeds bounded page limit")
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        raise CatalogUnavailable("Cannot verify current product price and stock") from None
