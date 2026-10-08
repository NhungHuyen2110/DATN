from utils.file_helper import load_json

def generate_brands():

    brands = load_json("data/brands.json")

    print("=" * 50)
    print("BRAND")
    print("=" * 50)

    for brand in brands:

        print(brand["id"], "-", brand["name"])

    return brands