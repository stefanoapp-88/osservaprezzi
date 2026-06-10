import json
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(
    page_title="OsservaPrezzi Carburanti",
    page_icon="⛽",
    layout="wide"
)

# ======================
# LOAD DATA
# ======================

@st.cache_data(ttl=300)
def load_data():

    df = pd.read_csv(
        "data/current_prices.csv"
    )

    try:
        with open(
            "data/last_update.json",
            "r",
            encoding="utf-8"
        ) as f:

            update = json.load(f)

    except:
        update = {}

    return df, update


df, update = load_data()

# Formattazione date

df["insertDate"] = pd.to_datetime(
    df["insertDate"],
    errors="coerce"
)



df["Aggiornato"] = (
    df["insertDate"]
    .dt.strftime("%d/%m %H:%M")
)

# ======================
# HEADER
# ======================

st.title("⛽ OsservaPrezzi Sicilia")


last_update = update.get(
    "last_update",
    "N/D"
)

try:

    last_update_fmt = (
        pd.to_datetime(last_update)
        .strftime("%d/%m/%Y %H:%M")
    )

except:

    last_update_fmt = last_update

st.info(
    f"🕒 Ultimo aggiornamento dati: {last_update_fmt}"
)

# ======================
# SIDEBAR
# ======================

st.sidebar.header("Filtri")

search_text = st.sidebar.text_input(
    "🔎 Cerca impianto"
)

province = st.sidebar.multiselect(
    "Provincia",
    sorted(df["province"].dropna().unique())
)

city_source = df.copy()

if province:

    city_source = city_source[
        city_source["province"].isin(
            province
        )
    ]

city = st.sidebar.multiselect(
    "Comune",
    sorted(
        [
            c
            for c in city_source["city"]
            .dropna()
            .unique()
            if str(c).strip()
        ]
    )
)



fuel = st.sidebar.multiselect(
    "Carburante",
    sorted(df["fuel"].dropna().unique())
)

brand = st.sidebar.multiselect(
    "Brand",
    sorted(df["brand"].dropna().unique())
)

mode = st.sidebar.selectbox(
    "Modalità",
    [
        "Tutti",
        "Self",
        "Servito"
    ]
)

# ======================
# FILTERS
# ======================

filtered = df.copy()

if province:
    filtered = filtered[
        filtered["province"].isin(province)
    ]

if city:
    filtered = filtered[
        filtered["city"].isin(city)
    ]

if fuel:
    filtered = filtered[
        filtered["fuel"].isin(fuel)
    ]

if brand:
    filtered = filtered[
        filtered["brand"].isin(brand)
    ]

if mode == "Self":
    filtered = filtered[
        filtered["isSelf"] == True
    ]

if mode == "Servito":
    filtered = filtered[
        filtered["isSelf"] == False
    ]

if search_text:

    txt = search_text.lower()

    filtered = filtered[

        filtered["stationName"]
        .astype(str)
        .str.lower()
        .str.contains(txt, na=False)

        |

        filtered["city"]
        .astype(str)
        .str.lower()
        .str.contains(txt, na=False)

        |

        filtered["brand"]
        .astype(str)
        .str.lower()
        .str.contains(txt, na=False)

        |

        filtered["stationId"]
        .astype(str)
        .str.contains(txt, na=False)

    ]

filtered["Modalità"] = filtered["isSelf"].map(
    {
        True: "Self",
        False: "Servito"
    }
)

# ======================
# KPI
# ======================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Impianti",
        filtered["stationId"].nunique()
    )

with col2:

    gasolio = filtered[
        filtered["fuel"]
        .str.contains(
            "Gasolio",
            case=False,
            na=False
        )
    ]

    if len(gasolio):

        st.metric(
            "Gasolio Min",
            f"€ {gasolio['price'].min():.3f}"
        )

with col3:

    benzina = filtered[
        filtered["fuel"]
        .str.contains(
            "Benzina",
            case=False,
            na=False
        )
    ]

    if len(benzina):

        st.metric(
            "Benzina Min",
            f"€ {benzina['price'].min():.3f}"
        )

with col4:

    st.metric(
        "Comuni",
        filtered["city"].nunique()
    )

st.divider()

st.subheader("🏆 Migliori impianti")

col_benzina, col_gasolio = st.columns(2)

with col_benzina:

    st.markdown("### ⛽ Benzina")

    top_benzina = (
    filtered[
        filtered["fuel"]
        .str.contains(
            "Benzina",
            case=False,
            na=False
        )
    ]
    .sort_values("price")
    .drop_duplicates(
        subset=["stationId"]
    )
    [
        [
            "stationName",
            "city",
            "price",
            "Aggiornato"
        ]
    ]
    .head(10)
    )

    st.write(top_benzina)

with col_gasolio:

    st.markdown("### 🚛 Gasolio")

    top_gasolio = (
    filtered[
        filtered["fuel"]
        .str.contains(
            "Gasolio",
            case=False,
            na=False
        )
    ]
    .sort_values("price")
    .drop_duplicates(
        subset=["stationId"]
    )
    [
        [
            "stationName",
            "city",
            "price",
            "Aggiornato"
        ]
    ]
    .head(10)
)

    st.write(top_gasolio)


# ======================
# MAPPA
# ======================

st.subheader("🗺️ Mappa impianti")

stations_map = (
    filtered
    .sort_values("price")
    .drop_duplicates(subset=["stationId"])
)

stations_map = stations_map.dropna(
    subset=["lat", "lng"]
)

st.write(
    f"Impianti visualizzati: {len(stations_map)}"
)

if len(stations_map) > 0:

    m = folium.Map()

    cluster = MarkerCluster().add_to(m)

    for _, row in stations_map.iterrows():

        station_rows = filtered[
            filtered["stationId"] == row["stationId"]
        ]

        fuel_lines = ""

        for _, fuel_row in station_rows.iterrows():

            tipo = (
                "Self"
                if fuel_row["isSelf"]
                else "Servito"
            )

            fuel_lines += (
                f"⛽ {fuel_row['fuel']} "
                f"{tipo}: "
                f"€ {fuel_row['price']}<br>"
            )

        popup = f"""
            <div style="width:260px">

            <b>{row['stationName']}</b><br>

            {row['city']}<br>
            {row['address']}<br><br>

            {fuel_lines}

            <hr>

            <b>Aggiornato:</b><br>
            {row['Aggiornato']}

            </div>
            """

        folium.Marker(
            location=[
                row["lat"],
                row["lng"]
            ],
            popup=popup
        ).add_to(cluster)

    bounds = [
        [
            stations_map["lat"].min(),
            stations_map["lng"].min()
        ],
        [
            stations_map["lat"].max(),
            stations_map["lng"].max()
        ]
    ]

    m.fit_bounds(bounds)

    st_folium(
        m,
        height=500,
        width=None
    )

# ======================
# TABELLA COMPLETA
# ======================

st.subheader("🔍 Ricerca impianti")

search = st.text_input(
    "Ricerca impianto / indirizzo"
)

if search:

    filtered = filtered[
        filtered["stationName"]
        .fillna("")
        .str.contains(
            search,
            case=False
        )
        |
        filtered["address"]
        .fillna("")
        .str.contains(
            search,
            case=False
        )
    ]

st.dataframe(

        filtered[
        [
            "stationName",
            "city",
            "address",
            "fuel",
            "price",
            "Modalità",
            "Aggiornato"
        ]
    ].sort_values(
        "price"
    ),

    use_container_width=True,
    hide_index=True
)