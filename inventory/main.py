import time
import requests
import json
import csv
import os
import schedule

SHEET_BASE_URL = "https://docs.google.com/spreadsheets/d/147HL4QCIvZX2amx6_Im6BiK4NwPTtFHxHf3mKN7k_S4"
SHEET_ID = "427318605"
SHEET_URL = f"{SHEET_BASE_URL}/export?format=csv&gid={SHEET_ID}"

CLIENTID = "b752c5a1-6c4c-4f64-a127-4e2c28cf08a2"

ZETTLE_PRODUCTS_ENDPOINT = "https://products.izettle.com/organizations/self/products/v2"
ZETTLE_INVENTORY_ENDPOINT = "https://inventory.izettle.com/v3/stock"
APIKEY = os.environ["ZETTLE_APIKEY"]

oauth_token = None

def download_sheet():
    res = requests.get(SHEET_URL)
    if res.status_code == 200:
        path = "data/components_sheet.csv"
        with open(path, "wb") as f:
            f.write(res.content)

def auth():
    global oauth_token
    res = requests.post(
        "https://oauth.zettle.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "client_id": CLIENTID,
            "assertion": APIKEY,
        }
    )
    oauth_token = res.json().get("access_token")



def parse_link_next(response):
    """Parse the Link header for the next page URL (cursor-based pagination)."""
    link_header = response.headers.get("Link", "")
    if 'rel="next"' in link_header:
        # Format: <https://...?cursor=xxx&limit=100>; rel="next"
        start = link_header.index("<") + 1
        end = link_header.index(">")
        return link_header[start:end]
    return None

def fetch_products():
    headers = {
        "Authorization": f"Bearer {oauth_token}"
    }
    all_products = []
    url = ZETTLE_PRODUCTS_ENDPOINT

    while url:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"Error fetching products: {res.status_code} - {res.text}")
            break
        all_products.extend(res.json())
        url = parse_link_next(res)
        if url:
            time.sleep(0.5)

    with open("data/zettle_products.json", "w") as f:
        json.dump(all_products, f)
    print(f"Fetched {len(all_products)} products")

def fetch_inventory():
    headers = {
        "Authorization": f"Bearer {oauth_token}"
    }
    all_inventory = []
    url = ZETTLE_INVENTORY_ENDPOINT

    while url:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"Error fetching inventory: {res.status_code} - {res.text}")
            break
        all_inventory.extend(res.json())
        url = parse_link_next(res)
        if url:
            time.sleep(0.5)

    with open("data/zettle_inventory.json", "w") as f:
        json.dump(all_inventory, f)
    print(f"Fetched {len(all_inventory)} inventory entries")
    


def load_sheetdata():
    with open("data/components_sheet.csv", "r") as f:
        reader = csv.DictReader(f)
        data = [row for row in reader]
    return data

def load_zettledata():
    with open("data/zettle_products.json", "r") as f:
        data = f.read()
    return json.loads(data)

def load_zettleinventory():
    with open("data/zettle_inventory.json", "r") as f:
        data = f.read()
    return json.loads(data)

SHEET_ONLY = 0
SHEET_ZETTLE_NOT_MATCHED = 1
SHEET_ZETTLE_MATCHED = 2
ZETTLE_ONLY = 3

class Product:
    def __init__(self, name, zettle_status):
        self.name = name
        self.unit = None
        self.price = 0
        self.location = None
        self.category = None # Like Microcontrollers, Sensor etc
        self.stock = 0
        self.zettle_status = zettle_status
        self.image_url = None
        self.mfg = None
        self.mpn = None
        self.description = None
        self.datasheet = None
        self.extra_link = None

def ensure_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)



def main():
    ensure_exists("data")
    ensure_exists("data_out")

    update_components()
    print("Scheduled next pull at 07:00")
    schedule.every().day.at("07:00").do(update_components)
    while True:
        schedule.run_pending()
        time.sleep(60*60)

def update_components():
    print("Get sheet")
    download_sheet()
    print("Zettle auth")
    auth()
    print("Get products")
    fetch_products()
    print("Get inventory")
    fetch_inventory()
    
    print("Loading data")
    sheet = load_sheetdata()
    zettle = load_zettledata()
    zettle_inventory = load_zettleinventory()

    zettle_products = []

    for product in zettle:
        name = product["name"]
        unit = product["unitName"]
        image = None
        if "presentation" in product.keys() and product["presentation"]["imageUrl"]:
            image = product["presentation"]["imageUrl"]
        for variant in product.get("variants", []):
            # if "PLA" in name:
            #     print(variant)
            #     print(unit)
            uuid = variant["uuid"]
            variantname = variant["name"]
            price = variant["price"]
            if price is None:
                price = 0
            else:
                price = float(price["amount"])/100

            nameout = name
            if variantname:
                nameout += f" {variantname}"

            res = {
                "name": nameout,
                "uuid": uuid,
                "unit": unit,
                "price": price,
                "image": image,
            }
            zettle_products.append(res)

    products = []
    for product in sheet:
        name = product["Name"]
        if name=="":
            # Was a workaround became a feature!
            # if name column left blank one can write whatever one wants in
            # other columns ;) Clever eh? Nice Griffin.
            continue
        in_zettle = product["In Zettle?"] != ""
        if in_zettle:
            zettle_status = SHEET_ZETTLE_NOT_MATCHED
        else:
            zettle_status = SHEET_ONLY
        p = Product(name, zettle_status)
        p.mfg = product["Manufacturer"]
        p.mpn = product["MPN"]
        p.description = product["Description"]
        p.location = product["Location"]
        p.category = product["Category"]
        p.datasheet = product["Datasheet"]
        p.extra_link = product["ExtraLink"]
        products.append(p)

    for zproduct in zettle_products:
    

        target_product = None
        for product in products:
            # strip down spaces and all bös. Compare RAW text...
            # Gets weird errors where excel or zettle has an extra space...
            if " ".join(product.name.split()).lower() == " ".join(zproduct["name"].split()).lower():
                product.zettle_status = SHEET_ZETTLE_MATCHED
                target_product = product
        if target_product is None:
            target_product = Product(zproduct["name"], ZETTLE_ONLY)
            products.append(target_product)

        target_product.unit = zproduct["unit"]
        target_product.price = zproduct["price"]
        target_product.image_url = zproduct["image"]
        for stock in zettle_inventory:
            if stock["variantUuid"] == zproduct["uuid"]:
                target_product.stock = stock["balance"]
                break

    zettle_only_count = 0
    sheet_only_count = 0

    for p in products:
        if p.zettle_status == SHEET_ZETTLE_NOT_MATCHED:
            print(f"Product in sheet not matched in zettle: {p.name}")
            sheet_only_count += 1
        elif p.zettle_status == ZETTLE_ONLY:
            print(f"Product only in Zettle: {p.name}")
            zettle_only_count += 1

    print(f"Total products only in sheet: {sheet_only_count}")
    print(f"Total products only in Zettle: {zettle_only_count}")

    with open("data_out/inventory.json", "w") as f:
        json.dump([{
            "name": p.name,
            "unit": p.unit,
            "price": p.price,
            "stock": p.stock,
            "zettle_status": p.zettle_status,
            "image_url": p.image_url,
            "mfg": p.mfg,
            "mpn": p.mpn,
            "description": p.description,
            "location": p.location,
            "category": p.category,
            "datasheet": p.datasheet,
            "extra_link": p.extra_link,
        } for p in products], f)

if __name__ == "__main__":
    main()
