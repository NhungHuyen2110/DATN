"""Read-only authoritative product snapshot from the existing Business API."""
import os
import requests
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from shared.observability import correlation_headers
from shared.verified_attributes import PublicAttribute
from shared.retrieval_limits import SourceGate

_catalog_gate=SourceGate('business-catalog',timeout=4,cooldown=10)
_last_catalog_failure=None


def catalog_source_status():
    return {'last_failure':_last_catalog_failure}


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
    global _last_catalog_failure
    if os.getenv('LUMIERE_RETRIEVAL_LIMITS_ENABLED','false').lower()=='true':
        try:
            value=_catalog_gate.call(_fetch_catalog)
            _last_catalog_failure=None
            return value
        except Exception as error:
            cause=error.__context__ if isinstance(error,CatalogUnavailable) else error
            _last_catalog_failure={'type':type(cause).__name__}
            from shared.retrieval_limits import SourceUnavailable
            if isinstance(error,SourceUnavailable):
                reasons={'Source is cooling down':'cooldown','Source already has a retrieval in flight':'busy',
                         'Retrieval exceeded its source time budget':'timeout'}
                _last_catalog_failure['reason']=reasons.get(str(error),'unavailable')
            raise CatalogUnavailable('Current catalog source unavailable within deadline') from None
    return _fetch_catalog()


def _fetch_catalog():
    base = os.getenv("BUSINESS_API_URL", "http://127.0.0.1:8001").rstrip("/")
    products = {}
    headers=correlation_headers()
    def page(number):
        # Separate short-lived sessions: requests.Session is not shared across
        # threads. At most two public GETs in flight; no retries or stale cache.
        with requests.Session() as client:
            client.trust_env=False
            response=client.get(base+'/products',params={'page':number,'page_size':100},timeout=3,headers=headers)
            response.raise_for_status()
            payload=response.json()
            items,total=payload['items'],payload['total']
            if type(total) is not int or not 0<=total<=5000 or not isinstance(items,list):
                raise ValueError('Invalid catalog page')
            expected=min(100,max(0,total-(number-1)*100))
            if len(items)!=expected:raise ValueError('Incomplete catalog page')
            return items,total
    try:
        first,total=page(1)
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='lumiere-catalog-page') as pool:
            pages=[(first,total),*pool.map(page,range(2,(total+99)//100+1))]
            for items,page_total in pages:
                if page_total!=total:raise ValueError('Catalog changed during pagination')
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
                    if 'verified_attributes' in item:
                        products[pid]['verified_attributes'] = [PublicAttribute.model_validate(fact).model_dump()
                                                               for fact in item['verified_attributes']]
        if len(products)!=total:raise ValueError('Catalog identity count changed')
        return products
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        raise CatalogUnavailable("Cannot verify current product price and stock") from None
