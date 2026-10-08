from utils.file_helper import load_json

def generate_collections():

    collections = load_json("data/collections.json")

    print("\n===== COLLECTION =====")

    for collection in collections:
        print(collection["id"], collection["name"])

    return collections