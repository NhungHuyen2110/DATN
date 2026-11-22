"""Public item-to-item recommendations; never read customer/order CSV or trust client identity."""
from .business_catalog import fetch_catalog
from .ranking import price_and_stock_valid, reciprocal_rank_fusion
from .search_service import verified_paths
from . import retrieval


def recommend_public(product_id, number):
    if type(number) is not int or not 1 <= number <= 20:
        raise ValueError('number must be 1..20')
    live = fetch_catalog()
    if product_id not in live:
        raise LookupError('Source product unavailable')
    source = live[product_id]
    eligible = {pid: item for pid, item in live.items() if pid != product_id and price_and_stock_valid(item, {})}
    rankings, evidence = {}, {}
    degraded = []
    # Deterministic structured baseline, no inferred Style/Audience or customer preference.
    structured = [(sum(item.get(key) == source.get(key) and source.get(key) is not None
                       for key in ('CategoryID', 'MaterialID', 'GemstoneID')), pid)
                  for pid, item in eligible.items()]
    rankings['structured'] = [pid for score, pid in sorted(structured, key=lambda pair: (-pair[0], pair[1])) if score]
    try:
        dense = retrieval.search_qdrant(' '.join(str(source.get(key, '')) for key in
            ('ProductName', 'Category', 'Material', 'Gemstone')), top_k=100, eligible_ids=list(eligible))
        rankings['dense'] = [int(item['ProductID']) for item in dense if int(item['ProductID']) in eligible]
    except Exception:
        degraded.append('dense_unavailable')
    try:
        graph = retrieval.graph_search_candidates('', {'reference_product': source, 'required_relationships': []})
        for item in graph:
            pid = int(item['ProductID'])
            if pid in eligible:
                paths = verified_paths(item.get('paths', []), eligible[pid], source)
                if paths:
                    evidence[pid] = paths
        rankings['graph'] = [int(item['ProductID']) for item in graph if int(item['ProductID']) in evidence]
    except Exception:
        degraded.append('graph_unavailable')
    latest = fetch_catalog()
    current_source = latest.get(product_id)
    if current_source is None or any(current_source.get(key) != source.get(key) for key in
                                   ('ProductName', 'CategoryID', 'MaterialID', 'GemstoneID')):
        raise LookupError('Source product changed; retry')
    result = []
    for pid, score, sources in reciprocal_rank_fusion(rankings):
        item = latest.get(pid)
        if item is None or not price_and_stock_valid(item, {}):
            continue
        # A stale structured-only candidate must still share a live attribute.
        shared = [key for key in ('CategoryID', 'MaterialID', 'GemstoneID')
                  if item.get(key) is not None and item.get(key) == current_source.get(key)]
        paths = verified_paths(evidence.get(pid, []), item, current_source)
        if not shared and 'dense' not in sources and not paths:
            continue
        result.append({'ProductID': pid, 'ProductName': item['ProductName'], 'CategoryName': item['Category'],
                       'MaterialName': item['Material'], 'GemstoneName': item['Gemstone'],
                       'SalePrice': str(item['Price']), 'Stock': item['Stock'], 'GraphEvidence': paths,
                       'verified_source': 'business_api'})
        if len(result) == number:
            break
    return result, degraded
