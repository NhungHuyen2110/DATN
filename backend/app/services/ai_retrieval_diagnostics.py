"""Server-to-server public-catalog diagnostics; never forwards browser credentials."""
import os
import requests
from fastapi import HTTPException
from shared.observability import correlation_headers


def retrieval_diagnostics(payload):
    token = os.getenv('LUMIERE_AI_DIAGNOSTICS_TOKEN', '')
    if not token:
        raise HTTPException(status_code=503, detail='Chẩn đoán AI chưa được cấu hình')
    base = os.getenv('LUMIERE_AI_INTERNAL_URL', 'http://127.0.0.1:8000').rstrip('/')
    try:
        response = requests.post(base + '/internal/retrieval-diagnostics', json=payload,
                                 headers={'Authorization': 'Bearer ' + token, **correlation_headers()}, timeout=15)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get('products'), list):
            raise ValueError('Invalid diagnostic response')
        allowed_fields = {'ProductID', 'ProductName', 'SKU', 'Category', 'CategoryID', 'Material', 'MaterialID',
                          'Gemstone', 'GemstoneID', 'Collection', 'Price', 'Stock', 'rank', 'score', 'score_type',
                          'rrf_score', 'rerank_features', 'graph_paths', 'retrieval_sources', 'matched_entities', 'reason'}
        return {'status': result.get('status'), 'requested_k': result.get('requested_k'),
                'returned_k': len(result['products']), 'understanding': result.get('understanding'),
                'diagnostics': result.get('diagnostics'),
                'products': [{key: value for key, value in item.items() if key in allowed_fields} for item in result['products']]}
    except (requests.RequestException, ValueError, TypeError):
        raise HTTPException(status_code=503, detail='Dịch vụ chẩn đoán AI tạm thời chưa sẵn sàng') from None
