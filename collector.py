import json
import logging
import re
import time


from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


# ==========================
# CONFIG
# ==========================

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

DATA_FOLDER = Path(CONFIG["data_folder"])
SNAPSHOT_FOLDER = Path(CONFIG["snapshot_folder"])
LOG_FOLDER = Path(CONFIG["log_folder"])

RADIUS_KM = CONFIG["radius_km"]
MAX_WORKERS = CONFIG["max_workers"]

ALLOWED_PROVINCES = CONFIG["allowed_provinces"]

DATA_FOLDER.mkdir(exist_ok=True)
SNAPSHOT_FOLDER.mkdir(parents=True, exist_ok=True)
LOG_FOLDER.mkdir(exist_ok=True)

# ==========================
# LOGGING
# ==========================

log_file = LOG_FOLDER / (
    f"collector_{datetime.now():%Y%m%d}.log"
)

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logging.info("START COLLECTOR")

# ==========================
# API
# ==========================

BASE_URL = "https://carburanti.mise.gov.it/ospzApi"

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://carburanti.mise.gov.it",
    "Referer": "https://carburanti.mise.gov.it/ospzSearch/zona",
    "User-Agent": "Mozilla/5.0"
}

# ==========================
# COMUNI
# ==========================

COMUNI = [

    # RG
    "RAGUSA",
    "MODICA",
    "VITTORIA",
    "COMISO",
    "SCICLI",
    "POZZALLO",
    "ISPICA",
    "ACATE",
    "CHIARAMONTE GULFI",
    "GIARRATANA",
    "MONTEROSSO ALMO",
    "SANTA CROCE CAMERINA",

    # CL
    "CALTANISSETTA",
    "GELA",
    "NISCEMI",
    "MUSSOMELI",
    "MAZZARINO",
    "SAN CATALDO",
    "RIESI",
    "SERRADIFALCO",
    "SOMMATINO",
    "DELIA",
    "BUTERA",
    "MILENA",
    "CAMPOFRANCO",
    "VALLELUNGA PRATAMENO"
]

# ==========================
# SEARCH POINTS
# ==========================

SEARCH_POINTS = [

    ("Ragusa", 36.9269, 14.7255),
    ("Modica", 36.8589, 14.7608),
    ("Vittoria", 36.9515, 14.5330),
    ("Comiso", 36.9486, 14.6070),
    ("Scicli", 36.7901, 14.7047),
    ("Pozzallo", 36.7305, 14.8469),
    ("Ispica", 36.7862, 14.9053),

    ("Caltanissetta", 37.4901, 14.0629),
    ("Gela", 37.0755, 14.2370),
    ("Niscemi", 37.1486, 14.3921),
    ("Mussomeli", 37.5778, 13.7522),
    ("Mazzarino", 37.3044, 14.2097),
    ("San Cataldo", 37.4848, 13.9847)
]

FUEL_TYPES = [
    "1-x",
    "2-x",
    "3-x",
    "4-x",
    "323-x",
    "324-x"
]

# ==========================
# HELPERS
# ==========================

def find_city(text):

    if not text:
        return ""

    text = text.upper()

    for city in COMUNI:
        if city in text:
            return city

    return ""


def extract_city_province(address):

    if not address:
        return "", ""

    province = ""

    province_match = re.search(
        r"\(([A-Z]{2})\)",
        address
    )

    if province_match:
        province = province_match.group(1)

    city = find_city(address)

    return city, province


# ==========================
# SEARCH STATIONS
# ==========================

stations = {}

print("\nRicerca impianti...")

for fuel_type in FUEL_TYPES:

    for name, lat, lng in SEARCH_POINTS:

        payload = {
            "points": [
                {
                    "lat": lat,
                    "lng": lng
                }
            ],
            "fuelType": fuel_type,
            "radius": RADIUS_KM
        }

        try:

            response = requests.post(
                f"{BASE_URL}/search/zone",
                headers=HEADERS,
                json=payload,
                timeout=30
            )

            response.raise_for_status()

            results = response.json().get(
                "results",
                []
            )

            for station in results:
                stations[station["id"]] = station

            print(
                f"{name} {fuel_type}: "
                f"{len(results)}"
            )

            time.sleep(0.2)

        except Exception as e:

            logging.error(
                f"SEARCH ERROR {name}: {e}"
            )

print(
    f"\nImpianti unici: {len(stations)}"
)

# ==========================
# DETAIL DOWNLOAD
# ==========================

download_time = datetime.now().isoformat()

def get_detail(item):

    station_id, station = item

    detail = None

    for attempt in range(5):

        try:

            response = requests.get(
                f"{BASE_URL}/registry/servicearea/{station_id}",
                timeout=30
            )

            response.raise_for_status()

            detail = response.json()

            break

        except requests.exceptions.HTTPError:

            if response.status_code == 429:

                wait_time = (attempt + 1) * 3

                print(
                    f"429 {station_id} - attendo {wait_time}s"
                )

                time.sleep(wait_time)

            else:

                logging.error(
                    f"DETAIL ERROR {station_id}: {response.status_code}"
                )

                return []

        except Exception as e:

            logging.error(
                f"DETAIL ERROR {station_id}: {e}"
            )

            return []

    if detail is None:

        logging.error(
            f"DETAIL ERROR {station_id}: too many retries"
        )

        return []

    address = detail.get("address", "")

    city = find_city(
        f"{detail.get('nomeImpianto','')} {address}"
    )

    city_from_address, province = (
        extract_city_province(address)
    )

    if not city:
        city = city_from_address

    if province not in ALLOWED_PROVINCES:
        return []

    lat = station.get("location", {}).get("lat")
    lng = station.get("location", {}).get("lng")

    services = detail.get("services", [])

    service_names = ", ".join(
        s.get("description", "")
        for s in services
    )

    rows = []

    for fuel in detail.get("fuels", []):

        rows.append({

            "downloadTime": download_time,
            "stationId": station_id,

            "stationName":
                detail.get(
                    "nomeImpianto",
                    detail.get("name", "")
                ),

            "brand": detail.get("brand", ""),
            "company": detail.get("company", ""),

            "address": address,
            "city": city,
            "province": province,

            "lat": lat,
            "lng": lng,

            "fuel": fuel.get("name"),
            "fuelId": fuel.get("fuelId"),
            "price": fuel.get("price"),
            "isSelf": fuel.get("isSelf"),

            "insertDate":
                fuel.get("insertDate"),

            "validityDate":
                fuel.get("validityDate"),

            "serviceCount":
                len(services),

            "serviceNames":
                service_names
        })

    return rows


rows = []

total = len(stations)

for idx, item in enumerate(
    stations.items(),
    start=1
):

    station_id = item[0]

    print(
        f"[{idx}/{total}] "
        f"Impianto {station_id}"
    )

    result = get_detail(item)

    rows.extend(result)

    time.sleep(0.30)

# ==========================
# SAVE FILES
# ==========================

df = pd.DataFrame(rows)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

snapshot_json = (
    SNAPSHOT_FOLDER /
    f"prices_{timestamp}.json"
)

snapshot_csv = (
    SNAPSHOT_FOLDER /
    f"prices_{timestamp}.csv"
)

current_json = (
    DATA_FOLDER /
    "current_prices.json"
)

current_csv = (
    DATA_FOLDER /
    "current_prices.csv"
)

df.to_csv(
    current_csv,
    index=False,
    encoding="utf-8-sig"
)

df.to_csv(
    snapshot_csv,
    index=False,
    encoding="utf-8-sig"
)

with open(
    current_json,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        rows,
        f,
        ensure_ascii=False,
        indent=2
    )

with open(
    snapshot_json,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        rows,
        f,
        ensure_ascii=False,
        indent=2
    )

last_update = {
    "last_update": download_time,
    "stations": len(stations),
    "records": len(rows)
}

with open(
    DATA_FOLDER / "last_update.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        last_update,
        f,
        ensure_ascii=False,
        indent=2
    )

logging.info(
    f"END stations={len(stations)} records={len(rows)}"
)

print("\n====================")
print("FINE")
print("====================")
print("Impianti:", len(stations))
print("Record:", len(rows))
print("JSON:", current_json)
print("CSV :", current_csv)