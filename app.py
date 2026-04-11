from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import numpy as np
import networkx as nx

app = FastAPI()

# ---------------- LOAD DATA ----------------
areas = pd.read_csv("realistic_100_areas.csv")
roads = pd.read_csv("realistic_100_roads.csv")

# ---------------- BUILD GRAPH ----------------
G = nx.Graph()
for _, row in roads.iterrows():
    cost = row['distance'] / row['capacity']
    G.add_edge(row['source'], row['destination'], weight=cost)


# ---------------- DASHBOARD ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard():

    options = "".join([f"<option value='{a}'>{a}</option>" for a in areas['area']])

    return f"""
    <html>
    <head>
        <title>AI Disaster Evacuation System</title>
        <style>
            body {{font-family: Arial; padding:40px; background:#f5f5f5;}}
            h1 {{color:#333;}}
            select,button {{padding:10px; margin-top:10px;}}
            pre {{background:white; padding:15px; border-radius:8px;}}
        </style>
    </head>
    <body>
        <h1>🚨 AI Disaster Evacuation Planner</h1>

        <label>Select Risk Area:</label><br>
        <select id="area">
            {options}
        </select>

        <br>
        <button onclick="run()">Generate Evacuation Plan</button>

        <pre id="output"></pre>

        <script>
        async function run(){{
            const area = document.getElementById('area').value;
            const res = await fetch('/evacuate?area=' + area);
            const data = await res.json();

            document.getElementById('output').textContent =
                JSON.stringify(data, null, 2);
        }}
        </script>
    </body>
    </html>
    """


# ---------------- EVACUATION LOGIC ----------------
@app.get("/evacuate")
def evacuate(area: str):

    # risk calculation
    areas['risk'] = (
        0.4 * areas['population_density'] +
        0.3 * areas['hazard_level'] +
        0.2 * areas['rainfall']
    )

    high_risk = areas.sort_values(by='risk', ascending=False)

    source = area

    safe_zones = high_risk.tail(3)['area'].values
    safe_zones = [z for z in safe_zones if z != source]

    routes = {}

    for zone in safe_zones:
        path = nx.shortest_path(G, source=source, target=zone, weight='weight')
        routes[zone] = path

    return {
        "Evacuate From": source,
        "Safe Zones": safe_zones,
        "Routes": routes
    }
