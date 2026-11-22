"""Dense + lexical + optional graph fusion, constrained by live Business data."""
import re
import unicodedata
import math
import time
from shared.observability import measure
from shared.retrieval_limits import SourceUnavailable

from .entity_linking import link_query, normalize
from .ranking import reciprocal_rank_fusion, finalize_topk, price_and_stock_valid, approved_facts, reviewed_constraints_valid
from shared.verified_attributes import reviews_enabled
from .query_reference import reference_request, resolve_reference


class RetrievalUnavailable(RuntimeError):
    pass


def measured_call(stage, function, *args, **kwargs):
    with measure(stage):
        return function(*args, **kwargs)


def verified_paths(paths, product, reference=None, anchors=None):
    fields = {'BELONGS_TO': ('CategoryID', 'Category'), 'HAS_GEMSTONE': ('GemstoneID', 'Gemstone'),
              'MADE_OF': ('MaterialID', 'Material')}
    result, seen = [], set()
    for path in paths:
        relation = path.get('relationship')
        if relation in {'HAS_STYLE', 'SUITABLE_FOR'}:
            if not reviews_enabled():
                continue
            label = 'Style' if relation == 'HAS_STYLE' else 'Audience'
            if path.get('target_label') != label:
                continue
            key = (label, path.get('target_id'))
            fact = approved_facts(product).get(key)
            if fact is None or path.get('evidence_sha256') != fact['source_reference_sha256']:
                continue
            source = reference
            if source is None and path.get('source_product_id') is not None:
                source = (anchors or {}).get(path['source_product_id'])
                if source is None:
                    continue
            if source is not None:
                source_fact = approved_facts(source).get(key)
                if (path.get('source_product_id') != source['ProductID']
                        or path.get('candidate_product_id') != product['ProductID'] or source_fact is None
                        or path.get('anchor_evidence_sha256') != source_fact['source_reference_sha256']):
                    continue
            if key not in seen:
                clean = {'relationship': relation, 'target_label': label, 'target_id': path['target_id'],
                         'target_name': fact['name'], 'evidence_sha256': fact['source_reference_sha256']}
                if source is not None:
                    clean.update(source_product_id=source['ProductID'], candidate_product_id=product['ProductID'],
                                 anchor_evidence_sha256=source_fact['source_reference_sha256'])
                result.append(clean)
                seen.add(key)
            continue
        if relation not in fields:
            continue
        id_field, name_field = fields[relation]
        if path.get('target_id') != product.get(id_field) or product.get(id_field) is None:
            continue
        source = reference
        if source is None and path.get('source_product_id') is not None:
            source = (anchors or {}).get(path['source_product_id'])
            if source is None:
                continue
        if source is not None and (path.get('source_product_id') != source['ProductID']
                or path.get('candidate_product_id') != product['ProductID'] or source.get(id_field) != path['target_id']):
            continue
        key = (relation, path['target_id'])
        if key not in seen:
            clean = {'relationship': relation, 'target_id': path['target_id'], 'target_name': product[name_field]}
            if source is not None:
                clean.update({'source_product_id': source['ProductID'], 'candidate_product_id': product['ProductID']})
            result.append(clean)
            seen.add(key)
    return result


def search(query, top_k, dense, catalog, parse_price, graph=None, *, sources=None,
           candidate_k=None, reranker=None, entity_encoder=None, diagnostics=False, lexical_retriever=None,
           graph_expander=None):
    started, timings = time.perf_counter(), {}
    def call(stage, function, *args, **kwargs):
        stage_start = time.perf_counter()
        try:
            return measured_call(stage, function, *args, **kwargs)
        finally:
            timings[stage] = timings.get(stage, 0) + time.perf_counter() - stage_start
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("top_k must be 1..10")
    count = re.search(r"\btop\s*(\d+)\b", normalize(query))
    if count:
        top_k = int(count.group(1))
        if not 1 <= top_k <= 10:
            raise ValueError("Requested top_k must be 1..10")
    selected = set(sources) if sources is not None else {'lexical', 'dense'} | ({'graph'} if graph else set())
    if not selected or not selected.issubset({'lexical', 'dense', 'graph'}):
        raise ValueError('Select lexical/dense/graph retrieval sources')
    pool_size = candidate_k if candidate_k is not None else max(top_k * 7, 35)
    if type(pool_size) is not int or not top_k <= pool_size <= 1000:
        raise ValueError('candidate_k must be requested K..1000')
    understanding = call('parse', link_query, query, encoder=entity_encoder)
    related = reference_request(query)
    if related['unsupported_style']:
        return {'products': [], 'status': 'missing_verified_attributes', 'understanding': understanding}
    if understanding["needs_clarification"] and not related['active']:
        return {"products": [], "status": "clarification_required", "understanding": understanding}
    unsupported = [e for e in understanding["entities"] if e["label"] in {"Audience", "Style"}]
    # Current catalog has no verified Audience/Style fields. Never pretend these
    # constraints were satisfied using gender stereotypes or collection names.
    if unsupported and not related['active'] and not reviews_enabled():
        return {"products": [], "status": "missing_verified_attributes", "understanding": understanding}
    try:
        live = call('catalog', catalog)
    except Exception:
        raise RetrievalUnavailable("Authoritative catalog unavailable") from None
    reference = None
    if related['active']:
        resolution = resolve_reference(query, live)
        if resolution['status'] != 'ok':
            if resolution.get('reason'):
                understanding['ambiguities'].append(resolution['reason'])
                understanding['needs_clarification'] = True
            return {'products': [], 'status': resolution['status'], 'understanding': understanding,
                    'requested_k': top_k, 'returned_k': 0}
        reference = resolution['product']
        # A source product's name may contain another category. It describes the
        # reference, not a second desired category (e.g. a ring like earring X).
        constraint_text = normalize(query).replace(normalize(reference['ProductName']), ' ')
        understanding = call('parse', link_query, constraint_text, encoder=entity_encoder)
        understanding['normalized_query'] = normalize(query)
        if understanding['needs_clarification']:
            return {'products': [], 'status': 'clarification_required', 'understanding': understanding}
        if not reviews_enabled() and any(item['label'] in {'Audience', 'Style'} for item in understanding['entities']):
            return {'products': [], 'status': 'missing_verified_attributes', 'understanding': understanding}
        understanding['reference_product'] = {key: reference.get(key) for key in
            ('ProductID', 'ProductName', 'CategoryID', 'MaterialID', 'GemstoneID')}
        if reviews_enabled():
            understanding['reference_product']['verified_attributes'] = reference.get('verified_attributes', [])
        understanding['required_relationships'] = related['relations']
    normalized = normalize(query)
    content_query = re.sub(r'\btop\s*\d+\b', ' ', query, flags=re.I)
    identifier_query = normalize(content_query)
    # Preserve compatibility with the existing money parser for unaccented text.
    money_query = "".join(c for c in unicodedata.normalize("NFD", query.casefold())
                          if unicodedata.category(c) != "Mn").replace("đ", "d")
    for source, target in (("duoi", "dưới"), ("tren", "trên"), ("trieu", "triệu"),
                           ("nghin", "nghìn"), ("tu", "từ"), ("den", "đến"),
                           ("ngan sach", "ngân sách"), ("khong qua", "không quá")):
        money_query = re.sub(r"(?<!\w)" + source + r"(?!\w)", target, money_query)
    # Keep original decimal punctuation; normalize() would split 8,5 into 8 5.
    constraints = dict(parse_price(query))
    if constraints.get("min_price") is None and constraints.get("max_price") is None:
        constraints = dict(parse_price(money_query))
    constraints["max_exclusive"] = bool(re.search(r"\bduoi\b", normalized))
    constraints["min_exclusive"] = bool(re.search(r"\btren\b", normalized))
    constraints["attributes"] = {}
    constraints['reviewed_attributes'] = {entity['label']: entity['canonical_id'] for entity in understanding['entities']
                                         if entity['label'] in {'Audience', 'Style'}}
    for label in constraints['reviewed_attributes']:
        if not any(any(key[0] == label for key in approved_facts(product)) for product in live.values()):
            return {'products': [], 'status': 'missing_verified_attributes', 'understanding': understanding}
    for entity in understanding["entities"]:
        if entity["label"] in {"Category", "Gemstone"}:
            constraints["attributes"][entity["label"] + "ID"] = entity["graph_id"]
    # A unique explicit SKU is an identity constraint, not merely one lexical
    # vote tied with an unrelated dense rank. Keep the same constraint during
    # final live verification in case a SKU changes while retrieval runs.
    if reference is None:
        explicit_sku = (bool(re.search(r'\bmã\b', query.casefold())) or 'sku' in normalized.split()
                        or any(phrase in normalized for phrase in ('ma san pham', 'ma sp', 'ma hang')))
        sku_matches = {item['SKU'] for item in live.values() if item.get('SKU')
                       and (explicit_sku or (any(character.isdigit() for character in item['SKU'])
                            and (not normalize(item['SKU']).isdigit() or identifier_query == normalize(item['SKU']))))
                       and ' ' + normalize(item['SKU']) + ' ' in ' ' + (normalized if explicit_sku else identifier_query) + ' '}
        if len(sku_matches) == 1:
            constraints['attributes']['SKU'] = next(iter(sku_matches))
    if reference is not None:
        required = {'HAS_GEMSTONE': 'GemstoneID', 'MADE_OF': 'MaterialID', 'BELONGS_TO': 'CategoryID'}
        for relation in related['relations']:
            if relation == 'HAS_STYLE':
                styles = sorted(key[1] for key in approved_facts(reference) if key[0] == 'Style')
                if not styles:
                    return {'products': [], 'status': 'missing_verified_attributes', 'understanding': understanding}
                if (constraints['reviewed_attributes'].get('Style') is not None
                        and constraints['reviewed_attributes']['Style'] not in styles):
                    understanding['ambiguities'].append('conflicting_reference_style')
                    understanding['needs_clarification'] = True
                    return {'products': [], 'status': 'clarification_required', 'understanding': understanding}
                constraints['shared_reference_styles'] = styles
                continue
            field, value = required[relation], reference.get(required[relation])
            if value is None:
                return {'products': [], 'status': 'missing_verified_attributes', 'understanding': understanding}
            if field in constraints['attributes'] and constraints['attributes'][field] != value:
                understanding['ambiguities'].append('conflicting_reference_' + field)
                understanding['needs_clarification'] = True
                return {'products': [], 'status': 'clarification_required', 'understanding': understanding}
            constraints['attributes'][field] = value
        if not related['relations'] and 'CategoryID' not in constraints['attributes']:
            constraints['attributes']['CategoryID'] = reference['CategoryID']
    # Respect explicit material phrases; the existing schema has these names.
    material_query = constraint_text if reference is not None else normalized
    materials = [name for name in ("vang trang 18k", "vang trang 14k", "vang trang 10k", "vang trang", "vang hong", "vang 24k", "vang 18k", "vang 14k", "vang 10k", "bach kim", "bac 925", "bac", "vang")
                 if " " + name + " " in " " + material_query + " "]
    required_material = max(materials, key=len) if materials else None
    if required_material:
        live = {pid: p for pid, p in live.items()
                if ' ' + required_material + ' ' in ' ' + normalize(p["Material"]) + ' '}
    # Filter with current authoritative data BEFORE dense search, then verify again
    # at finalization. Otherwise a small semantic pool can contain only products
    # outside the budget, discarding useful dense ranks after retrieval.
    eligible = {pid: p for pid, p in live.items() if price_and_stock_valid(p, constraints)
                and reviewed_constraints_valid(p, constraints)
                and (reference is None or pid != reference['ProductID'])
                and all(p.get(field) == value for field, value in constraints['attributes'].items())}
    # Requested result count is a planner control, not a product-name token.
    # Explicit SKU wording is retained because a legitimate code may be TOP3.
    retrieval_query = query if reference is None and explicit_sku else content_query
    if reference is not None:
        retrieval_query += ' ' + ' '.join(str(reference.get(key, '')) for key in
                                        ('ProductName', 'Category', 'Material', 'Gemstone'))
    tokens = set(normalize(retrieval_query).split()) - {"top", "tim", "cho", "toi", "san", "pham", "duoi", "trieu", "nghin"}
    lexical = []
    for pid, product in (eligible.items() if 'lexical' in selected and lexical_retriever is None else []):
        representation = normalize(" ".join(str(product.get(field, "")) for field in
                                           ("SKU", "ProductName", "Category", "Material", "Gemstone", "Collection")))
        if reviews_enabled():
            representation += ' ' + normalize(' '.join(fact['name'] for fact in approved_facts(product).values()))
        hits = len(tokens.intersection(representation.split()))
        if hits:
            lexical.append((hits, pid))
    lexical.sort(key=lambda pair: (-pair[0], pair[1]))
    rankings = {"lexical": [pid for _, pid in lexical[:pool_size]]} if 'lexical' in selected else {}
    if 'lexical' in selected and lexical_retriever is not None:
        rankings['lexical'] = [pid for pid in call('lexical', lexical_retriever, query,
                              eligible_ids=list(eligible), top_k=pool_size) if pid in eligible][:pool_size]
    degraded, source_errors = [], {}
    def source_failure(name, error):
        # Internal diagnostics expose controlled codes, never raw exception text/URLs/queries.
        source_errors[name] = {'error_type': type(error).__name__}
        if isinstance(error, SourceUnavailable):
            reasons = {'Source is cooling down': 'cooldown',
                       'Source already has a retrieval in flight': 'in_flight',
                       'Retrieval exceeded its source time budget': 'timeout'}
            source_errors[name]['reason'] = reasons.get(str(error), 'unavailable')
    if 'dense' in selected:
        try:
            rankings["dense"] = [int(p["ProductID"]) for p in call('dense', dense, retrieval_query, top_k=pool_size,
                                                                   eligible_ids=list(eligible))
                                 if p.get("ProductID") is not None and int(p['ProductID']) in eligible]
        except Exception as error:
            degraded.append("dense_unavailable")
            source_failure('dense', error)
    evidence = {}
    if 'graph' in selected:
        try:
            if graph is None:
                raise RetrievalUnavailable('Graph adapter not configured')
            graph_products = call('graph', graph, query, understanding)
            evidence = {int(p['ProductID']): verified_paths(p.get('paths', []), eligible[int(p['ProductID'])], reference)
                        for p in graph_products if int(p['ProductID']) in eligible}
            rankings["graph"] = [int(p['ProductID']) for p in graph_products
                                 if evidence.get(int(p['ProductID']))][:pool_size]
        except Exception as error:
            degraded.append("graph_unavailable")
            source_failure('graph', error)
        # Dense candidates are real anchors, before fusion or final Top-K.
        # Explicit reference requests retain their stricter reference traversal.
        anchor_ids = list(dict.fromkeys(rankings.get('dense', [])))[:pool_size]
        if graph_expander is not None and anchor_ids and reference is None:
            try:
                expanded = call('graph', graph_expander, anchor_ids, top_k=pool_size)
                anchor_products = {pid: eligible[pid] for pid in anchor_ids}
                accepted = []
                for item in expanded:
                    pid = item.get('ProductID')
                    if pid not in eligible:
                        continue
                    paths = verified_paths(item.get('paths', []), eligible[pid], anchors=anchor_products)
                    if paths:
                        evidence.setdefault(pid, []).extend(paths)
                        accepted.append(pid)
                rankings['graph'] = list(dict.fromkeys(rankings.get('graph', []) + accepted))[:pool_size]
            except Exception as error:
                if 'graph_unavailable' not in degraded:
                    degraded.append('graph_unavailable')
                source_failure('graph', error)
    fused = [{"ProductID": pid, "score": score, "retrieval_sources": sources,
              "score_type": "rrf", "graph_paths": evidence.get(pid, [])}
             for pid, score, sources in call('fusion', reciprocal_rank_fusion, rankings)]
    latest = live
    latest_reference = reference
    if fused:
        try:
            latest = call('verification', catalog)
            if reference is not None:
                latest_reference = latest.get(reference['ProductID'])
        except Exception:
            raise RetrievalUnavailable('Cannot revalidate catalog before returning results') from None
        if required_material:
            latest = {pid: p for pid, p in latest.items()
                      if ' ' + required_material + ' ' in ' ' + normalize(p['Material']) + ' '}
    for candidate in fused:
        candidate['graph_paths'] = verified_paths(candidate['graph_paths'], latest.get(candidate['ProductID'], {}),
                                                   reference, anchors=latest)
    if reference is not None and fused:
        current_reference = latest_reference
        if current_reference is None:
            return {'products': [], 'status': 'reference_unavailable', 'understanding': understanding,
                    'requested_k': top_k, 'returned_k': 0}
        if any(current_reference.get(field) != reference.get(field) for field in
               ('ProductName', 'CategoryID', 'MaterialID', 'GemstoneID', *(
                   ('verified_attributes',) if 'HAS_STYLE' in related['relations'] else ()))):
            return {'products': [], 'status': 'reference_changed', 'understanding': understanding,
                    'requested_k': top_k, 'returned_k': 0}
    if reranker is not None and fused:
        rerank_input = [
            {**item, **latest[item['ProductID']], 'score': item['score']} for item in fused
            if item['ProductID'] in latest and price_and_stock_valid(latest[item['ProductID']], constraints)
            and reviewed_constraints_valid(latest[item['ProductID']], constraints)
            and all(latest[item['ProductID']].get(field) == value for field, value in constraints['attributes'].items())]
        if rerank_input:
            reranked = call('rerank', reranker, query, rerank_input)
            expected = {item['ProductID'] for item in rerank_input}
            actual = [item.get('ProductID') for item in reranked]
            if (len(actual) != len(expected) or set(actual) != expected
                    or any(not math.isfinite(float(item.get('score', float('nan')))) for item in reranked)):
                raise ValueError('Reranker changed identities or returned invalid scores')
            fused = reranked
    products = finalize_topk(fused, top_k, constraints, latest)
    for product in products:
        matched = [e for e in understanding['entities'] if e['label'] in {'Category', 'Gemstone', 'Audience', 'Style'}]
        product['matched_entities'] = [{'label': e['label'], 'canonical_id': e['canonical_id']} for e in matched]
        reasons = []
        if 'CategoryID' in constraints['attributes']:
            reasons.append('đúng loại ' + product['Category'])
        if 'GemstoneID' in constraints['attributes']:
            reasons.append('đúng loại đá ' + product['Gemstone'])
        if constraints.get('max_price') is not None or constraints.get('min_price') is not None:
            reasons.append('trong khoảng giá yêu cầu')
        for label, canonical in constraints['reviewed_attributes'].items():
            reasons.append('có nhãn ' + approved_facts(product)[(label, canonical)]['name'] + ' đã được xác nhận')
        if reference is not None:
            reasons.append('thuộc tính được đối soát với sản phẩm #' + str(reference['ProductID']))
        relation_names = {'BELONGS_TO': 'cùng danh mục', 'MADE_OF': 'cùng chất liệu',
                          'HAS_GEMSTONE': 'cùng loại đá', 'HAS_STYLE': 'cùng phong cách',
                          'SUITABLE_FOR': 'cùng đối tượng sử dụng'}
        for path in product.get('graph_paths', [])[:2]:
            if path.get('source_product_id') is not None:
                reasons.append(relation_names[path['relationship']] + ' ' + path['target_name']
                               + ' với sản phẩm #' + str(path['source_product_id']))
        product['reason'] = '; '.join(reasons + ['giá và tồn kho được kiểm tra từ dữ liệu bán hàng hiện tại'])
    result = {"products": products, "status": "degraded" if degraded else "ok",
            "degraded": degraded, "requested_k": top_k, "returned_k": len(products),
            "understanding": understanding}
    if diagnostics:
        result['diagnostics'] = {'source_ranks': rankings, 'source_errors': source_errors, 'candidate_k': pool_size,
                                 'eligible_products': len(eligible), 'candidate_union': len(fused),
                                 'timings_seconds': timings, 'total_seconds': time.perf_counter() - started,
                                 'reranker': getattr(reranker, 'name', None)}
    return result
