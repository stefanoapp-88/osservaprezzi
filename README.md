# OsservaPrezzi Sicilia

Dashboard e sistema di raccolta prezzi carburanti per la Sicilia.

## Componenti

* `collector.py` → scarica e normalizza i dati dei carburanti
* `app.py` → dashboard Streamlit
* `data/current_prices.json` → dati correnti
* `data/last_update.json` → timestamp ultimo aggiornamento

## Avvio dashboard

```bash
streamlit run app.py
```

## Aggiornamento dati

```bash
python collector.py
```

## Tecnologie

* Python
* Pandas
* Streamlit
* GitHub
* Windows Server 2019
