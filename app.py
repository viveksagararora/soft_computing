from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import numpy as np
import networkx as nx

app = FastAPI()

# ---------------- DATA ----------------
areas = pd.read_csv("realistic_100_areas.csv")
roads = pd.read_csv("realistic_100_roads.csv")
weather = pd.read_csv("weatherHistory.csv")
earthquake = pd.read_csv("database.csv")

# ---------------- GRAPH ----------------
G = nx.Graph()
for _, row in roads.iterrows():
    cost = row['distance'] + (1 / max(row['capacity'],1))
    G.add_edge(row['source'], row['destination'], weight=cost)

# ---------------- RISK ----------------
def calculate_risk():
    weather_score = (
        0.4 * weather['Humidity'].mean() +
        0.3 * weather['Wind Speed (km/h)'].mean() +
        0.2 * weather['Loud Cover'].mean()
    )

    earthquake_score = earthquake['Magnitude'].mean()

    raw_risk = (
        0.3 * areas['population_density'] +
        0.25 * areas['hazard_level'] +
        0.2 * areas['rainfall'] +
        0.15 * weather_score +
        0.1 * earthquake_score
    )

    areas['risk'] = 100 * (raw_risk - raw_risk.min()) / (raw_risk.max() - raw_risk.min())
    return areas.sort_values(by='risk', ascending=False)

# ---------------- GA ----------------
def genetic_distribution(n, total_people):
    vals = np.random.dirichlet(np.ones(n))[0]
    perc = [round(v*100,2) for v in vals]
    ppl = [int(v*total_people) for v in vals]
    return perc, ppl

# ---------------- PAGE 1 ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    options = "<option disabled selected>Select Area</option>" + "".join(
        [f"<option value='{a}'>{a}</option>" for a in areas['area']]
    )

    return f"""
    <html>
    <body style="text-align:center;font-family:sans-serif">
    <h1>🚨 RescueNet</h1>

    <form action="/risk_page">
        <select name="area" required>{options}</select><br><br>
        <button>Analyze Risk</button>
    </form>

    </body>
    </html>
    """

# ---------------- PAGE 2 ----------------
@app.get("/risk_page", response_class=HTMLResponse)
def risk_page(area:str):
    data = calculate_risk()
    selected = data[data['area']==area].iloc[0]
    safe = data.tail(3)

    html = f"<h2>Risk Score: {selected['risk']:.2f}</h2>"
    html += "<h3>Safe Zones:</h3>"

    for _, row in safe.iterrows():
        html += f"<p>{row['area']} (Risk: {row['risk']:.2f})</p>"

    html += f"""
    <form action="/crowd_page">
        <input type="hidden" name="area" value="{area}">
        <button>Next</button>
    </form>
    """

    return f"<html><body style='text-align:center'>{html}</body></html>"

# ---------------- PAGE 3 ----------------
@app.get("/crowd_page", response_class=HTMLResponse)
def crowd_page(area:str):
    return f"""
    <html>
    <body style="text-align:center">

    <h2>Enter Crowd Size</h2>

    <form action="/distribution_page">
        <input type="hidden" name="area" value="{area}">
        <input name="people" required><br><br>
        <button>Distribute</button>
    </form>

    </body>
    </html>
    """

# ---------------- PAGE 4 ----------------
@app.get("/distribution_page", response_class=HTMLResponse)
def distribution_page(area:str, people:int):
    data = calculate_risk()
    safe = data.tail(3)['area'].values

    perc, ppl = genetic_distribution(3, int(people))

    html = "<h2>Crowd Distribution</h2>"

    for i in range(3):
        html += f"<p>{safe[i]} → {perc[i]}% ({ppl[i]} people)</p>"

    html += f"""
    <form action="/routes_input">
        <input type="hidden" name="area" value="{area}">
        <button>Next</button>
    </form>
    """

    return f"<html><body style='text-align:center'>{html}</body></html>"

# ---------------- PAGE 5 ----------------
@app.get("/routes_input", response_class=HTMLResponse)
def routes_input(area:str):
    return f"""
    <html>
    <body style="text-align:center">

    <h2>Enter Number of Routes</h2>

    <form action="/routes_page">
        <input type="hidden" name="area" value="{area}">
        <input name="k" required><br><br>
        <button>Generate Routes</button>
    </form>

    </body>
    </html>
    """

# ---------------- PAGE 6 ----------------
@app.get("/routes_page", response_class=HTMLResponse)
def routes_page(area:str, k:int):
    data = calculate_risk()
    safe = data.tail(k)['area'].values

    all_paths = []

    for zone in safe:
        path = nx.dijkstra_path(G, area, zone, weight='weight')

        if len(path) > 12:
            path = path[:12] + ["..."]

        cost = nx.path_weight(G, path[:-1] if "..." in path else path, weight='weight')
        all_paths.append((cost, path))

    all_paths.sort(key=lambda x: x[0])

    best = all_paths[0][1]
    others = [p[1] for p in all_paths[1:]]

    html = "<h2>⭐ Best Route</h2>"
    html += "<p>" + " → ".join(best) + "</p>"

    html += "<h3>Other Routes</h3>"
    for r in others:
        html += "<p>" + " → ".join(r) + "</p>"

    return f"<html><body style='text-align:center'>{html}</body></html>"
