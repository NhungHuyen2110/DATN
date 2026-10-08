from utils.file_helper import load_json

def generate_gemstones():

    gemstones = load_json("data/gemstones.json")

    print("\n===== GEMSTONE =====")

    for gemstone in gemstones:
        print(gemstone["id"], gemstone["name"])

    return gemstones