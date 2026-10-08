from utils.file_helper import load_json

def generate_materials():

    materials = load_json("data/materials.json")

    print("\n===== MATERIAL =====")

    for material in materials:
        print(material["id"], material["name"])

    return materials