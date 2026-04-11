from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import numpy as np
import networkx as nx

app = FastAPI()

# ---------------- LOAD DATASETS ----------------
areas = pd.read_csv("realistic_100_areas.csv")
roads = pd.read_csv("realistic_100_roads.csv")
weather = pd.read_csv("weatherHistory.csv")
earthquake = pd.read_csv("database.csv")
population = pd.read_csv("csvData.csv")

# ---------------- BUILD GRAPH ----------------
G = nx.Graph()
for _, row in roads.iterrows():
    cost = row['distance'] / row['capacity']
    G.add_edge(row['source'], row['destination'], weight=cost)

# ---------------- GENETIC DISTRIBUTION ----------------
def genetic_distribution(n):
    vals = np.random.dirichlet(np.ones(n), size=1)[0]
    return [round(v * 100, 2) for v in vals]


# ---------------- DASHBOARD ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard():

    options = "".join([f"<option value='{a}'>{a}</option>" for a in areas['area']])

    return f"""
    <html>
    <head>
        <title>AI Disaster Evacuation Planner</title>
        <style>
            body {{font-family: Arial; padding:40px; background:#f5f5f5;}}
            select,button {{padding:10px;margin:5px}}
            .card {{background:white;padding:20px;border-radius:10px;margin-top:20px}}
            h1 {{color:#333}}
        </style>
    </head>
    <body>

    <h1>🚨 AI Disaster Evacuation Planner</h1>

    <label>Select Risk Area:</label><br>
    <select id="area">{options}</select>
    <button onclick="run()">Generate Evacuation Plan</button>

    <div id="output"></div>

    <script>
    async function run(){{
        const area = document.getElementById('area').value;
        const res = await fetch('/evacuate?area=' + area);
        const data = await res.json();

        let html = "<div class='card'>";
        html += "<h3>Evacuate From: " + data.source + "</h3>";
        html += "<h4>Safe Zones:</h4> " + data.safe_zones.join(", ");

        html += "<h4>Crowd Distribution:</h4>";
        for (let k in data.distribution){{
            html += "<br>➡ " + k + " : " + data.distribution[k] + " %";
        }}

        html += "<h4>Optimized Routes:</h4>";
        for (let k in data.routes){{
            html += "<br><b>" + k + "</b>: " + data.routes[k].join(" → ");
        }}

        html += "</div>";

        document.getElementById("output").innerHTML = html;
    }}
    </script>

    </body>
    </html>
    """


# ---------------- EVACUATION LOGIC ----------------
@app.get("/evacuate")
def evacuate(area: str):

    # Weather risk
    weather_score = (
        0.4 * weather['Humidity'].mean() +
        0.3 * weather['Wind Speed (km/h)'].mean() +
        0.2 * weather['Loud Cover'].mean()
    ) * 0.01

    # Earthquake risk
    earthquake_score = earthquake['Magnitude'].mean() * 0.01

    # Combined risk
    areas['risk'] = (
        0.3 * areas['population_density'] +
        0.25 * areas['hazard_level'] +
        0.2 * areas['rainfall'] +
        weather_score +
        earthquake_score
    )

    high_risk = areas.sort_values(by='risk', ascending=False)

    source = area

    safe_zones = high_risk.tail(3)['area'].values
    safe_zones = [z for z in safe_zones if z != source]

    routes = {}

    for zone in safe_zones:
        path = nx.shortest_path(G, source=source, target=zone, weight='weight')
        routes[zone] = path

    # Genetic distribution
    distribution_values = genetic_distribution(len(safe_zones))

    distribution = {
        safe_zones[i]: distribution_values[i]
        for i in range(len(safe_zones))
    }

    return {
        "source": source,
        "safe_zones": safe_zones,
        "routes": routes,
        "distribution": distribution
    }
