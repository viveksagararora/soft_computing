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
    cost = row['distance'] / row['capacity']
    G.add_edge(row['source'], row['destination'], weight=cost)

# ---------------- RISK FUNCTION ----------------
def calculate_risk():

    weather_score = (
        0.4 * weather['Humidity'].mean() +
        0.3 * weather['Wind Speed (km/h)'].mean() +
        0.2 * weather['Loud Cover'].mean()
    ) * 0.01

    earthquake_score = earthquake['Magnitude'].mean() * 0.01

    areas['risk'] = (
        0.3 * areas['population_density'] +
        0.25 * areas['hazard_level'] +
        0.2 * areas['rainfall'] +
        weather_score +
        earthquake_score
    )

    return areas.sort_values(by='risk', ascending=False)

# ---------------- GA ----------------
def genetic_distribution(n, total_people):
    vals = np.random.dirichlet(np.ones(n), size=1)[0]
    perc = [round(v*100,2) for v in vals]
    people = [int(v*total_people) for v in vals]
    return perc, people


# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard():

    options = "".join([f"<option value='{a}'>{a}</option>" for a in areas['area']])

    return f"""
    <html>
    <head>
    <title>AI Evacuation System</title>

    <style>
    body {{
        font-family: Arial;
        background: linear-gradient(135deg,#667eea,#764ba2);
        padding:30px;
        color:white;
    }}

    .card {{
        background:white;
        color:black;
        padding:20px;
        border-radius:10px;
        margin-top:20px;
    }}

    button {{
        padding:10px;
        margin-top:10px;
        background:#4a47a3;
        color:white;
        border:none;
        border-radius:5px;
        cursor:pointer;
    }}

    input, select {{
        padding:10px;
        margin-top:10px;
    }}
    </style>

    </head>

    <body>

    <h1>🚨 AI Disaster Evacuation System</h1>

    <!-- STEP 1 -->
    <div class="card">
    <h3>Step 1: Select Risk Area</h3>
    <select id="area">{options}</select>
    <button onclick="analyze()">Analyze Risk</button>
    </div>

    <!-- STEP 2 -->
    <div id="risk_output"></div>

    <!-- STEP 3 -->
    <div id="crowd_input"></div>

    <!-- STEP 4 -->
    <div id="distribution_output"></div>

    <!-- STEP 5 -->
    <div id="routes_output"></div>

    <script>

    async function analyze(){{
        let area = document.getElementById("area").value;
        let res = await fetch('/risk?area='+area);
        let data = await res.json();

        let html = `<div class='card'>
        <h3>Risk Score: ${data.risk.toFixed(2)}</h3>
        <h4>Safe Zones:</h4>`;

        data.safe_zones.forEach(z => {{
            html += `<p>${z.name} (Risk: ${z.risk.toFixed(2)})</p>`;
        }});

        html += "</div>";

        document.getElementById("risk_output").innerHTML = html;

        document.getElementById("crowd_input").innerHTML =
        `<div class='card'>
        <h3>Step 2: Enter Crowd Size</h3>
        <input id='people' placeholder='Enter number of people'/>
        <button onclick="distribute()">Distribute Crowd</button>
        </div>`;
    }}

    async function distribute(){{
        let people = document.getElementById("people").value;
        let area = document.getElementById("area").value;

        let res = await fetch(`/distribution?area=${area}&people=${people}`);
        let data = await res.json();

        let html = `<div class='card'><h3>Crowd Distribution</h3>`;

        for(let i=0;i<data.safe_zones.length;i++){{
            html += `<p>${data.safe_zones[i]} → ${data.percentage[i]}% (${data.people[i]} people)</p>`;
        }}

        html += `<button onclick="routes()">Generate Routes</button></div>`;

        document.getElementById("distribution_output").innerHTML = html;
    }}

    async function routes(){{
        let area = document.getElementById("area").value;

        let res = await fetch(`/routes?area=${area}`);
        let data = await res.json();

        let html = `<div class='card'><h3>Optimized Routes</h3>`;

        for(let k in data.routes){{
            html += `<p><b>${k}</b>: ${data.routes[k].join(" → ")}</p>`;
        }}

        html += "</div>";

        document.getElementById("routes_output").innerHTML = html;
    }}

    </script>

    </body>
    </html>
    """


# ---------------- API: RISK ----------------
@app.get("/risk")
def risk(area:str):

    high_risk = calculate_risk()

    selected = high_risk[high_risk['area']==area].iloc[0]

    safe = high_risk.tail(3)

    safe_zones = [
        {"name": row['area'], "risk": row['risk']}
        for _, row in safe.iterrows()
    ]

    return {
        "risk": selected['risk'],
        "safe_zones": safe_zones
    }


# ---------------- API: DISTRIBUTION ----------------
@app.get("/distribution")
def distribution(area:str, people:int):

    high_risk = calculate_risk()
    safe = high_risk.tail(3)['area'].values

    perc, ppl = genetic_distribution(len(safe), int(people))

    return {
        "safe_zones": list(safe),
        "percentage": perc,
        "people": ppl
    }


# ---------------- API: ROUTES ----------------
@app.get("/routes")
def routes(area:str):

    high_risk = calculate_risk()
    safe = high_risk.tail(3)['area'].values

    routes = {}

    for zone in safe:
        path = nx.shortest_path(G, source=area, target=zone, weight='weight')
        routes[zone] = path

    return {"routes": routes}
