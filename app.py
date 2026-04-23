from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import pandas as pd
import numpy as np
import networkx as nx

app = FastAPI()

# ---------------- LOAD DATA ----------------
areas = pd.read_csv("realistic_100_areas.csv")
roads = pd.read_csv("realistic_100_roads.csv")
weather = pd.read_csv("weatherHistory.csv")
earthquake = pd.read_csv("database.csv")

# ---------------- GRAPH ----------------
G = nx.Graph()
for _, row in roads.iterrows():
    # ✅ FIXED COST (distance priority)
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

    # ✅ Normalize 0–100
    areas['risk'] = 100 * (raw_risk - raw_risk.min()) / (raw_risk.max() - raw_risk.min())

    return areas.sort_values(by='risk', ascending=False)

# ---------------- GA ----------------
def genetic_distribution(n, total_people):
    vals = np.random.dirichlet(np.ones(n), size=1)[0]
    perc = [round(v*100,2) for v in vals]
    ppl = [int(v*total_people) for v in vals]
    return perc, ppl

# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard():

    options = "".join([f"<option value='{a}'>{a}</option>" for a in areas['area']])

    return f"""
    <html>
    <head>
    <title>RescueNet</title>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
    body {{
        font-family: 'Segoe UI';
        background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
        color:white;
        text-align:center;
        padding:40px;
    }}

    .card {{
        background:white;
        color:black;
        padding:25px;
        border-radius:12px;
        max-width:600px;
        margin:20px auto;
    }}

    input, select {{
        width:100%;
        padding:10px;
        margin-top:10px;
    }}

    button {{
        width:100%;
        padding:12px;
        margin-top:15px;
        background:#0077ff;
        color:white;
        border:none;
        border-radius:6px;
        font-weight:bold;
    }}

    .best {{
        background:#d4edda;
        padding:10px;
        border-radius:6px;
        margin-top:10px;
    }}
    </style>

    </head>

    <body>

    <h1>🚨 RescueNet</h1>

    <div class="card">
        <select id="area">{options}</select>
        <input id="people" placeholder="Enter number of people">
        <input id="routesCount" placeholder="Number of routes (e.g. 3)">
        <button onclick="run()">Generate Plan</button>
    </div>

    <div id="output"></div>

    <script>

    async function run(){{
        let area = document.getElementById("area").value;
        let people = document.getElementById("people").value;
        let k = document.getElementById("routesCount").value || 3;

        let riskData = await (await fetch('/risk?area='+area)).json();
        let distData = await (await fetch('/distribution?area='+area+'&people='+people)).json();
        let routeData = await (await fetch('/routes?area='+area+'&k='+k)).json();

        let html = "<div class='card'>";
        html += "<h3>Risk Score: " + riskData.risk.toFixed(2) + "</h3>";

        html += "<h4>Safe Zones</h4><canvas id='riskChart'></canvas>";
        html += "<h4>Crowd Distribution</h4><canvas id='distChart'></canvas>";

        html += "<h4>Routes</h4>";

        // BEST ROUTE
        html += "<div class='best'><b>⭐ Best Route:</b><br>" +
                routeData.best.join(" → ") + "</div>";

        // OTHER ROUTES
        for(let i=0;i<routeData.others.length;i++){{
            html += "<p>Alternative Route " + (i+1) + ": " +
                    routeData.others[i].join(" → ") + "</p>";
        }}

        html += "</div>";

        document.getElementById("output").innerHTML = html;

        // Charts
        new Chart(document.getElementById("riskChart"), {{
            type: 'bar',
            data: {{
                labels: riskData.safe_zones.map(z => z.name),
                datasets: [{{
                    label: 'Risk',
                    data: riskData.safe_zones.map(z => z.risk)
                }}]
            }}
        }});

        new Chart(document.getElementById("distChart"), {{
            type: 'bar',
            data: {{
                labels: distData.safe_zones,
                datasets: [{{
                    label: 'People %',
                    data: distData.percentage
                }}]
            }}
        }});
    }}

    </script>

    </body>
    </html>
    """

# ---------------- APIs ----------------

@app.get("/risk")
def risk(area:str):
    data = calculate_risk()
    selected = data[data['area']==area].iloc[0]
    safe = data.tail(3)

    safe_zones = [
        {"name": row['area'], "risk": float(row['risk'])}
        for _, row in safe.iterrows()
    ]

    return {"risk": float(selected['risk']), "safe_zones": safe_zones}


@app.get("/distribution")
def distribution(area:str, people:int):
    data = calculate_risk()
    safe = data.tail(3)['area'].values

    perc, ppl = genetic_distribution(len(safe), int(people))

    return {"safe_zones": list(safe), "percentage": perc, "people": ppl}


@app.get("/routes")
def routes(area:str, k:int=3):
    data = calculate_risk()
    safe = data.tail(k)['area'].values

    all_paths = []

    for zone in safe:
        path = nx.dijkstra_path(G, area, zone, weight='weight')

        # limit path length
        if len(path) > 12:
            path = path[:12] + ["..."]

        cost = nx.path_weight(G, path[:-1] if "..." in path else path, weight='weight')
        all_paths.append((cost, path))

    all_paths.sort(key=lambda x: x[0])

    best = all_paths[0][1]
    others = [p[1] for p in all_paths[1:]]

    return {"best": best, "others": others}
