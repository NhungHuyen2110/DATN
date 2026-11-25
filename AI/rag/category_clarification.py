"""Server-owned clarification of close ontology-vector matches, no answer bank."""
import re
from jewelry_agents.entity_linking import load_entities,link_query,normalize
from jewelry_agents.intent_router import classify_query


# def category_question(query,scores):
#     ranked=sorted(scores.items(),key=lambda item:(-item[1],item[0]))
#     if len(ranked)<2 or ranked[0][1]<.60 or ranked[0][1]-ranked[1][1]>=.10:return None
#     ontology={e['canonical_id']:e for e in load_entities()['entities'] if e['label']=='Category'}
#     options=[{'canonical_id':key,'name':ontology[key]['aliases'][0],'similarity':score} for key,score in ranked[:2]]
#     return {'success':True,'intent':'shopping_clarification','status':'clarification_required','products':[],
#             'answer':'Mô tả của bạn gần với hai loại trang sức: '+
#                      '; '.join(f"{i+1}. {option['name']}" for i,option in enumerate(options))+'. '+
#                      'Bạn muốn chọn loại nào? Mình sẽ giữ các điều kiện bạn đã nêu.',
#             'clarification_options':options,'query_planning_method':'ontology_embedding_ambiguity'}


def category_question(query, scores):
    from jewelry_agents.ontology_reasoner import reason_categories

    evidence = reason_categories(query)

    ontology = {
        e["canonical_id"]: e
        for e in load_entities()["entities"]
        if e["label"] == "Category"
    }

    if evidence["status"] == "resolved":
        return None

    if evidence["status"] == "ambiguous":
        eligible = set(evidence["eligible"])

        ranked = sorted(
            [
                (key, scores.get(key))
                for key in eligible
                if key in ontology
            ],
            key=lambda item: (
                -(item[1] if item[1] is not None else -1),
                item[0],
            ),
        )

        method = "ontology_constraint_ambiguity"

    else:
        ranked = sorted(
            [
                (key, score)
                for key, score in scores.items()
                if key in ontology
            ],
            key=lambda item: (-item[1], item[0]),
        )

        if (
            len(ranked) < 2
            or ranked[0][1] < .60
            or ranked[0][1] - ranked[1][1] >= .10
        ):
            return None

        method = "ontology_embedding_ambiguity"

    if len(ranked) < 2:
        return None

    options = [
        {
            "canonical_id": key,
            "name": ontology[key]["aliases"][0],
            "similarity": score,
        }
        for key, score in ranked[:2]
    ]

    return {
        "success": True,
        "intent": "shopping_clarification",
        "status": "clarification_required",
        "products": [],
        "answer": (
            "Bạn muốn chọn loại trang sức nào: "
            + "; ".join(
                f"{i + 1}. {option['name']}"
                for i, option in enumerate(options)
            )
            + "? Mình sẽ giữ các điều kiện bạn đã nêu."
        ),
        "clarification_options": options,
        "query_planning_method": method,
    }



def pending_category_reply(message,row,tool):
    pending=row.get('pending_category')
    if not pending:return None
    from shared.conversation import knowledge_request,followup_kind
    if (knowledge_request(message) or followup_kind(message) or
            classify_query(message) in {'restricted_request','shipping_policy','unverified_policy','customer_order_guidance','out_of_scope'}):
        return None
    options=pending['options']
    from jewelry_agents.shopping_advice import followup_query,standalone_budget
    mentions=link_query(message)['entities']
    if standalone_budget(message) or len(mentions)==1 and mentions[0]['label']=='Gemstone':
        updated=followup_query(message,pending['query'])
        if updated!=message:
            pending['query']=updated
            row['shopping_context']=updated
            return {'success':True,'intent':'shopping_clarification','status':'clarification_required','products':[],
                    'answer':'Mình đã giữ điều kiện mới. Bạn chọn loại trang sức trong các phương án vừa nêu nhé.',
                    'clarification_options':options}
    selected=None;method=None
    related_reply=False;classified_reply=False
    # text=normalize(message)
    # if not re.search(r'\b(?:khong|dung)\b',text):
    text = normalize(message)

    import unicodedata

    original_text = unicodedata.normalize(
        "NFC", message
    ).casefold()

    has_negation = bool(
        re.search(
            r"\b(?:không|khong|đừng|chẳng|chang)\b",
            original_text
        )
    )

    if not has_negation:
        explicit=[e for e in link_query(message)['entities'] if e['label']=='Category']
        if len(explicit)==1:
            selected=next((o for o in options if o['canonical_id']==explicit[0]['canonical_id']),None)
            # method='explicit_category'
            method = (
                'ontology_reply_constraint'
                if explicit[0].get('method') == 'ontology_constraint'
                else 'explicit_category'
            )    
            if selected is None:
                row.pop('pending_category',None)
                return None  # A new category is processed by normal shopping followups.
        if not explicit:
            match=re.fullmatch(r'(?:(?:loai|mau|phuong an|cai)\s*)?(?:thu\s*)?(1|2|nhat|hai|dau tien)(?:\s+(?:nhe|a|di))?',text)
            if match:
                index=0 if match.group(1) in {'1','nhat','dau tien'} else 1
                if index<len(options):selected=options[index];method='option_selection'
            elif len(message)<=120:
                try:
                    from jewelry_agents.retrieval import _dense_gate,get_dense_services
                    from jewelry_agents.semantic_category import category_links
                    def operation():
                        from jewelry_agents.advice_planner import plan_advice
                        model=get_dense_services()[1]
                        advice=plan_advice(message,model,include_embedding=True)
                        context=advice['_request_embedding']
                        links=context.entity_links or category_links(message,model,context.vector)
                        return links,bool(advice['accepted'] and advice['intent'] in {'gift_advice','product_search'})
                    links,related_reply=_dense_gate.call(operation)
                    classified_reply=True
                    if links:
                        selected=next((o for o in options if o['canonical_id']==links[0].canonical_id),None)
                        method='ontology_reply_embedding'
                # except Exception:pass
                # except Exception:
                #     import traceback
                #     traceback.print_exc()
                except Exception:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Semantic category reply unavailable"
                    )
    if selected:
        effective=pending['query']+' '+selected['name']
        if len(effective)>1000:
            return {'success':True,'intent':'shopping_clarification','status':'clarification_required','products':[],
                    'answer':'Bạn rút gọn yêu cầu giúp mình, giữ loại trang sức và ngân sách để tìm đúng nhé.'}
        row.pop('pending_category',None)
        result=tool(effective)
        result['clarification_resolution']={'canonical_id':selected['canonical_id'],'method':method}
        return result
    # if (classified_reply and not related_reply and not re.search(r'\b(?:khong|dung)\b',text)
    if (classified_reply and not related_reply and not has_negation 
            and not mentions and not any(term in text for term in ('chua hieu','chua ro'))):
        row.pop('pending_category',None)
        return None
    # Do not keep unrelated conversations stuck in a clarification branch.
    if len(message)>120 or len(text.split())>12:
        row.pop('pending_category',None)
        return None
    ontology={e['canonical_id']:e for e in load_entities()['entities'] if e['label']=='Category'}
    descriptions=[ontology[o['canonical_id']]['definition'] for o in options]
    return {'success':True,'intent':'shopping_clarification','status':'clarification_required','products':[],
            'answer':'\n'.join(descriptions)+'\nBạn chọn một loại hoặc mô tả rõ vị trí muốn đeo nhé.',
            'clarification_options':options}
