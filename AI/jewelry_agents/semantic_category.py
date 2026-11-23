"""Ontology-definition vector linking, not a question/answer lookup.

Only Category nodes with existing server graph IDs can be proposed. Abstain on
low confidence, close alternatives, explicit category aliases, or negation.
"""
from dataclasses import dataclass
import threading
from weakref import WeakKeyDictionary
import re
from .entity_linking import cosine,load_entities,link_query,normalize

_cache=WeakKeyDictionary()
_lock=threading.Lock()


@dataclass(frozen=True)
class CategoryLink:
    canonical_id:str
    graph_id:int
    similarity:float
    margin:float


def _definition_vectors(encoder):
    definitions=[e for e in load_entities()['entities'] if e['label']=='Category' and e.get('definition')]
    signature=tuple((e['canonical_id'],e['definition']) for e in definitions)
    with _lock:
        cached=_cache.get(encoder)
        if cached is None or cached[0]!=signature:
            values=encoder.encode([e['definition'] for e in definitions],batch_size=1)
            if len(values)!=len(definitions):raise ValueError('Invalid ontology embeddings')
            cached=(signature,values)
            _cache[encoder]=cached
    return definitions,cached[1]


def warm_category_definitions(encoder):
    _definition_vectors(encoder)


def category_links(query,encoder,vector,threshold=.60,margin=.10,evidence_scores=None):
    definitions,values=_definition_vectors(encoder)
    if any(e['label']=='Category' for e in link_query(query)['entities']):return ()
    text=normalize(query)
    text=re.sub(r'\bkhong qua\s+[\d.,]+\s*(?:trieu|nghin|tr|dong|vnd)\b',' ',text)
    text=re.sub(r'\bkhong biet\b',' ',text)
    if re.search(r'\b(?:khong|dung)\b',text):return ()
    ranked=sorted([(cosine(vector,value),entity) for entity,value in zip(definitions,values)],
                  key=lambda pair:(-pair[0],pair[1]['canonical_id']))
    if evidence_scores is not None:evidence_scores.update({entity['canonical_id']:score for score,entity in ranked})
    if len(ranked)<2:return ()
    score,entity=ranked[0]
    gap=score-ranked[1][0]
    if score<threshold or gap<margin:return ()
    return (CategoryLink(entity['canonical_id'],entity['graph_id'],score,gap),)


def merge_category_links(understanding,context,query):
    from .advice_planner import RequestEmbedding
    if not isinstance(context,RequestEmbedding) or context.query!=query:
        raise ValueError('Semantic evidence must belong to this exact request')
    result={**understanding,'entities':list(understanding['entities'])}
    if any(e['label']=='Category' for e in result['entities']):return result
    ontology={e['canonical_id']:e for e in load_entities()['entities'] if e['label']=='Category'}
    if len(context.entity_links)>1:raise ValueError('Ambiguous semantic category evidence')
    for link in context.entity_links:
        if not isinstance(link,CategoryLink):raise ValueError('Invalid category evidence type')
        entity=ontology.get(link.canonical_id)
        if (not entity or entity['graph_id']!=link.graph_id
                or not .60<=link.similarity<=1.000001 or not .10<=link.margin<=2):
            raise ValueError('Invalid semantic category evidence')
        result['entities'].append({'label':'Category','canonical_id':link.canonical_id,'graph_id':link.graph_id,
            'method':'embedding_ontology_definition','similarity':link.similarity,'margin':link.margin,'alias':None})
    return result
