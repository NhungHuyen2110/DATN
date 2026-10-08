from generators.category_generator import generate_categories
from generators.brand_generator import generate_brands
from generators.material_generator import generate_materials
from generators.gemstone_generator import generate_gemstones
from generators.collection_generator import generate_collections
from generators.supplier_generator import generate_suppliers
from generators.product_generator import generate_products

def main():

    categories = generate_categories()

    brands = generate_brands()

    materials = generate_materials()

    gemstones = generate_gemstones()

    collections = generate_collections()

    suppliers = generate_suppliers()

    products=generate_products()


    print()

    print(len(categories))

    print(len(brands))

    print(len(materials))

    print(len(gemstones))

    print(len(collections))

    print(len(suppliers))

    print(len(products))

if __name__=="__main__":
    main()