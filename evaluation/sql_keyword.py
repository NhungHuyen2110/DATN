"""Read-only PostgreSQL ILIKE baseline; terms/IDs/limit are bound parameters.

Unlike embedding retrieval, this deliberately does not infer synonyms or strip
Vietnamese accents. Callers supply the same live eligible IDs as other modes.
"""
import re
import unicodedata


def keyword_candidates(connection, query, eligible_ids, top_k=35):
    from sqlalchemy import bindparam, text
    if (len(query) > 1000 or type(top_k) is not int or not 1 <= top_k <= 1000
            or len(eligible_ids) > 5000
            or any(type(pid) is not int or pid <= 0 for pid in eligible_ids)):
        raise ValueError('Invalid bounded SQL baseline arguments')
    terms = list(dict.fromkeys(re.findall(r'\w+', unicodedata.normalize('NFC', query).casefold())))
    stop = {'top', 'tìm', 'tim', 'cho', 'tôi', 'toi', 'sản', 'san', 'phẩm', 'pham',
            'dưới', 'duoi', 'triệu', 'trieu', 'nghìn', 'nghin'}
    terms = [term for term in terms if term not in stop and not term.isdigit()][:32]
    if not terms or not eligible_ids:
        return []
    scores, parameters = [], {'eligible': list(dict.fromkeys(eligible_ids)), 'limit': top_k}
    for index, term in enumerate(terms):
        key = 'term_' + str(index)
        scores.append("CASE WHEN representation ILIKE :" + key + " ESCAPE '\\' THEN 1 ELSE 0 END")
        parameters[key] = '%' + term.replace('\\', '\\\\').replace('_', '\\_').replace('%', '\\%') + '%'
    statement = text('''WITH public_catalog AS (
        SELECT p.id, concat_ws(' ', p.sku, p.name, c.name, m.name, g.name, cl.name) AS representation
        FROM products p JOIN categories c ON c.id=p.category_id
        JOIN materials m ON m.id=p.material_id JOIN gemstones g ON g.id=p.gemstone_id
        JOIN collections cl ON cl.id=p.collection_id WHERE p.id IN :eligible
        ), scored AS (SELECT id, ''' + ' + '.join(scores) + ''' AS keyword_hits FROM public_catalog)
        SELECT id FROM scored WHERE keyword_hits > 0 ORDER BY keyword_hits DESC, id ASC LIMIT :limit
        ''').bindparams(bindparam('eligible', expanding=True))
    return list(connection.execute(statement, parameters).scalars())
