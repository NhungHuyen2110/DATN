"""Versioned, non-destructive product indexing. Inject model/client for tests."""
import hashlib
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.verified_attributes import normalize_projected_attributes
from shared.product_index_contract import VECTOR_FIELDS, embedding_document, document_sha256


def index_identity(model_name, model_revision, dimension):
    if not model_revision or dimension < 1:
        raise ValueError("Explicit embedding revision and positive dimension required")
    fingerprint = hashlib.sha256(f"{model_name}:{model_revision}:{dimension}:cosine".encode()).hexdigest()
    return "jewelry_products_v_" + fingerprint[:12], fingerprint


def product_payload(row, fingerprint, model_name, model_revision, source_sha256):
    payload = {
        **{field: row[source] for field, source in VECTOR_FIELDS.items()},
        'embedding_fingerprint': fingerprint, 'embedding_model': model_name,
        'embedding_revision': model_revision, 'source_sha256': source_sha256,
        'source_row': row['source_row'],
    }
    if 'verified_attributes' in row:
        payload['verified_attributes'] = normalize_projected_attributes(row['verified_attributes'])
        payload['embedding_document_version'] = 2
    payload['embedding_document_sha256'] = document_sha256(row, payload)
    return payload


def index_products(client, encoder, records, model_name, model_revision, source_sha256, batch_size=100,
                   reuse_existing=False):
    from qdrant_client.models import Distance, PointStruct, VectorParams
    dimension = encoder.get_sentence_embedding_dimension()
    collection, fingerprint = index_identity(model_name, model_revision, dimension)
    if not records or not 1 <= batch_size <= 10000:
        raise ValueError("Nonempty validated records and batch-size 1..10000 required")
    if client.collection_exists(collection):
        config = client.get_collection(collection).config.params.vectors
        if isinstance(config, dict) or config.size != dimension or config.distance != Distance.COSINE:
            raise ValueError("Existing collection schema differs; refusing to mix embeddings")
    else:
        client.create_collection(collection, vectors_config=VectorParams(size=dimension, distance=Distance.COSINE))
    reused = refreshed = 0
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        if reuse_existing:
            existing = {point.id: point for point in client.retrieve(
                collection, ids=[row['ProductID'] for row in batch], with_payload=True, with_vectors=True)}
            pending = []
            for row in batch:
                point = existing.get(row['ProductID'])
                expected = product_payload(row, fingerprint, model_name, model_revision, source_sha256)
                vector = point.vector if point is not None else None
                identity = ('embedding_fingerprint', 'embedding_model', 'embedding_revision', 'embedding_document_sha256')
                if (point is not None and all((point.payload or {}).get(k) == expected[k] for k in identity)
                        and isinstance(vector, list) and len(vector) == dimension
                        and all(math.isfinite(float(x)) for x in vector) and any(float(x) for x in vector)):
                    reused += 1
                    if point.payload != expected:
                        # Snapshot lineage/price/stock/review metadata does not
                        # change the document. Refresh payload, retain vector.
                        client.upsert(collection, points=[PointStruct(id=row['ProductID'], vector=vector,
                                                                      payload=expected)], wait=True)
                        refreshed += 1
                else:
                    pending.append(row)
            batch = pending
            if not batch:
                continue
        payloads = [product_payload(row, fingerprint, model_name, model_revision, source_sha256) for row in batch]
        texts = [embedding_document(row, payload) for row, payload in zip(batch, payloads)]
        vectors = encoder.encode(texts)
        if len(vectors) != len(batch):
            raise ValueError("Encoder returned wrong number of vectors")
        points = []
        for row, vector, payload in zip(batch, vectors, payloads):
            if len(vector) != dimension:
                raise ValueError("Encoder dimension drift")
            if not all(math.isfinite(float(x)) for x in vector) or not any(float(x) for x in vector):
                raise ValueError("Invalid cosine vector")
            points.append(PointStruct(id=row['ProductID'], vector=[float(x) for x in vector], payload=payload))
        client.upsert(collection, points=points, wait=True)
    imported = client.retrieve(collection, ids=[row['ProductID'] for row in records], with_payload=True, with_vectors=False)
    expected = {row['ProductID']: product_payload(row, fingerprint, model_name, model_revision, source_sha256)
                for row in records}
    return {'collection': collection, 'fingerprint': fingerprint, 'dimension': dimension, 'metric': 'COSINE',
            'reused_products': reused, 'refreshed_payload_products': refreshed,
            'encoded_products': len(records) - reused,
            'requested_products': len(records), 'verified_products': len(imported),
            'pass': len(imported) == len(records)
                    and {p.id for p in imported} == set(expected)
                    and all(p.id in expected and all((p.payload or {}).get(k) == v
                            for k, v in expected[p.id].items()) for p in imported)}
