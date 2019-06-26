import json
from typing import Dict

# used to keep track of uniques codes generated
from geoimagenet_api.utils import make_codes_from_name

all_codes = set()


def generate(dataset: str) -> Dict:
    """Insert taxonomy 4-letter codes in a json file containing taxonomies."""
    data = json.load(open(dataset))

    def insert_code_recursive(taxo):
        name = taxo["name"]["fr"]
        possible_codes = make_codes_from_name(name)
        for code in possible_codes:
            if not len(code) == 4:
                raise RuntimeError("Coding error: the code should be 4 letter long")
            if code not in all_codes:
                all_codes.add(code)
                taxo["code"] = code
                break
        else:
            print(f"No possible code for name: {name}")

        for child in taxo.get("value", []):
            insert_code_recursive(child)

    insert_code_recursive(data)

    return data


if __name__ == '__main__':
    datasets = ["couverture_de_sol_v1_a.json", "objets_v1_a.json"]
    outputs = ["couverture_de_sol_v1_b.json", "objets_v1_b.json"]
    for dataset, output in zip(datasets, outputs):
        data = generate(dataset)
        json.dump(data, open(output, "w"), ensure_ascii=False, indent=4)
