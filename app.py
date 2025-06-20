import streamlit as st
import requests
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import time

# === API-Zugriff ===
API_KEY = "6644c2e2a0a82cb772a3f7cbcc3d7398"
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

st.set_page_config(page_title="WettBot Greg – Einfach & Effektiv", layout="wide")
st.title("🏀 WettBot Greg – Einfach & Effektiv")

# === API-Statusprüfung ===
def check_api_status():
    url = f"{BASE_URL}/status"
    try:
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            st.success("✅ API-Verbindung erfolgreich")
        else:
            st.error(f"❌ API-Problem – Statuscode: {res.status_code}")
    except Exception as e:
        st.error(f"❌ API nicht erreichbar: {e}")

check_api_status()

# === Funktionen ===
def lade_odds_bet365(fixture_id):
    url = f"{BASE_URL}/odds?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return []
    return res.json().get("response", [])

def lade_xg_daten(fixture_id):
    url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return None
    daten = res.json().get("response", [])
    if not daten or len(daten) < 2:
        return None
    xg_home, xg_away = None, None
    for stat in daten:
        for eintrag in stat.get("statistics", []):
            if eintrag.get("type") == "Expected Goals":
                if stat["team"]["id"] == daten[0]["team"]["id"]:
                    xg_home = float(eintrag.get("value", 0))
                else:
                    xg_away = float(eintrag.get("value", 0))
    return xg_home, xg_away

def berechne_echten_value(quote, wahrscheinlichkeit):
    faire_quote = 1 / wahrscheinlichkeit if wahrscheinlichkeit > 0 else 0
    return round((faire_quote - quote) / quote * 100, 2)

def confidence_berechnen(quote):
    return round(min(1.0, 1 / float(quote)), 2)

@st.cache_data(show_spinner=False)
def generiere_kandidaten():
    kandidaten = []
    for i in range(7):  # Nächste 7 Tage
        datum = (datetime.datetime.now() + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"{BASE_URL}/fixtures?date={datum}"
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            continue
        spiele = res.json().get("response", [])

        for spiel in spiele:
            fixture_id = spiel["fixture"]["id"]
            home = spiel["teams"]["home"]
            away = spiel["teams"]["away"]
            teamname = f"{home['name']} - {away['name']}"
            odds_data = lade_odds_bet365(fixture_id)
            time.sleep(1)

            xg_home, xg_away = lade_xg_daten(fixture_id) or (None, None)

            if odds_data:
                for bookmaker in odds_data[0].get("bookmakers", []):
                    if bookmaker.get("id") == 6:
                        for bet in bookmaker.get("bets", []):
                            if bet.get("name") == "Match Winner":
                                for val in bet.get("values", []):
                                    if val["value"] in ["1", "2", "X", "Home", "Away", "Draw"]:
                                        try:
                                            quote = float(val["odd"])
                                            if xg_home is not None and xg_away is not None:
                                                if val["value"] in ["1", "Home"]:
                                                    wahrscheinlichkeit = xg_home / (xg_home + xg_away)
                                                elif val["value"] in ["2", "Away"]:
                                                    wahrscheinlichkeit = xg_away / (xg_home + xg_away)
                                                else:
                                                    wahrscheinlichkeit = 1 - abs(xg_home - xg_away) / (xg_home + xg_away)
                                            else:
                                                wahrscheinlichkeit = confidence_berechnen(quote)
                                            confidence = wahrscheinlichkeit
                                            value = berechne_echten_value(quote, confidence)
                                            kandidaten.append({
                                                "Spiel": teamname,
                                                "Datum": spiel["fixture"]["date"][:10],
                                                "Quote": quote,
                                                "Confidence": confidence,
                                                "Value": value
                                            })
                                        except:
                                            continue
    return kandidaten

# === Kandidaten laden ===
kandidaten = generiere_kandidaten()
df = pd.DataFrame(kandidaten)

# === Top-Kombis anzeigen ===
st.subheader("🎯 Automatisch gefundene Top-Kombis")

if not df.empty:
    if st.button("🔁 Neu mischen"):
        kombi = df.sample(min(5, len(df)))
    else:
        kombi = df.sample(min(5, len(df)))
    gesamtquote = kombi["Quote"].product()
    pot_gewinn = 5 * gesamtquote
    st.dataframe(kombi.reset_index(drop=True))
    st.success(f"✅ 5er-Kombi – Gesamtquote: {gesamtquote:.2f}, potenzieller Gewinn: {pot_gewinn:.2f} €")
else:
    st.warning("Keine passenden Spiele gefunden.")

# === Value-Verlauf anzeigen ===
st.subheader("📊 Quoten- & Value-Verlauf")
if not df.empty:
    df_sorted = df.sort_values("Datum")
    df_sorted["Datum"] = pd.to_datetime(df_sorted["Datum"])
    fig, ax1 = plt.subplots()
    ax1.plot(df_sorted["Datum"], df_sorted["Quote"], color="tab:blue")
    ax1.set_ylabel("Quote", color="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(df_sorted["Datum"], df_sorted["Value"], color="tab:orange")
    ax2.set_ylabel("Value (%)", color="tab:orange")
    fig.tight_layout()
    st.pyplot(fig)

# === Eigene Kombi-Analyse ===
st.subheader("🧠 Eigene Kombi analysieren")
eingabe = st.text_area("Eigene Tipps eingeben (z. B. Team A - Team B, Quote)", 
                       "Deutschland - Portugal, 1.85\nSpanien - Frankreich, 2.40")

eigene_tipps = []
for zeile in eingabe.split("\n"):
    teile = zeile.split(",")
    if len(teile) == 2:
        spiel = teile[0].strip()
        try:
            quote = float(teile[1].strip())
            confidence = confidence_berechnen(quote)
            value = berechne_echten_value(quote, confidence)
            eigene_tipps.append({"Spiel": spiel, "Quote": quote, "Confidence": confidence, "Value": value})
        except:
            continue

if eigene_tipps:
    df_user = pd.DataFrame(eigene_tipps)
    gesamtquote = df_user["Quote"].product()
    pot_gewinn = 5 * gesamtquote
    gesamterfolg = df_user["Confidence"].prod() * 100
    st.subheader("📈 Ergebnisanalyse")
    st.dataframe(df_user)
    st.markdown(f"**Gesamtquote:** {gesamtquote:.2f}")
    st.markdown(f"**Pot. Gewinn bei 5 € Einsatz:** {pot_gewinn:.2f} €")
    st.markdown(f"**Gesamteingeschätzte Wahrscheinlichkeit:** {gesamterfolg:.2f}%")
    if gesamterfolg < 10:
        st.error("🔴 Hohes Risiko – diese Kombi solltest du besser vermeiden.")
    elif gesamterfolg < 30:
        st.info("🟡 Mittleres Risiko – die Kombi könnte Value enthalten.")
    else:
        st.success("🟢 Gutes Value – solide Analyse, vielversprechende Kombi.")
