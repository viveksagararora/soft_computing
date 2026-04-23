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
    cost = row['distance'] / max(row['capacity'],1)
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

    # 🔥 Normalize to 0–100
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
    <title>RescueNet - AI Evacuation System</title>

    <style>
    body {{
        margin:0;
        font-family: 'Segoe UI';
        background: linear-gradient(135deg,#0f2027,#203a43,#2c5364);
        color:white;
    }}

    .header {{
        text-align:center;
        padding:20px;
        font-size:28px;
        font-weight:bold;
    }}

    .container {{
        max-width:1000px;
        margin:auto;
    }}

    .card {{
        background:white;
        color:black;
        padding:20px;
        border-radius:12px;
        margin-top:20px;
        box-shadow:0 10px 25px rgba(0,0,0,0.3);
        animation: fadeIn 0.5s ease-in-out;
    }}

    button {{
        padding:12px;
        background:#0077ff;
        color:white;
        border:none;
        border-radius:6px;
        cursor:pointer;
        width:100%;
        margin-top:10px;
        font-weight:bold;
    }}

    button:hover {{
        background:#005fcc;
    }}

    input, select {{
        padding:10px;
        margin-top:10px;
        width:100%;
        border-radius:6px;
        border:1px solid #ccc;
    }}

    .badge {{
        display:inline-block;
        padding:6px 10px;
        border-radius:6px;
        background:#ff4d4d;
        color:white;
        font-weight:bold;
    }}

    @keyframes fadeIn {{
        from {{opacity:0; transform:translateY(10px);}}
        to {{opacity:1; transform:translateY(0);}}
    }}
    </style>

    </head>

    <body>

    <div class="header">🚨 RescueNet - Smart Evacuation System</div>

    <div class="container">

    <div class="card">
    <h3>Step 1: Select Risk Area</h3>
    <select id="area">{options}</select>
    <button onclick="analyze()">Analyze Risk</button>
    </div>

    <div id="risk_output"></div>
    <div id="crowd_input"></div>
    <div id="distribution_output"></div>
    <div id="routes_output"></div>

    </div>

    <script>

    async function analyze(){{
        let area = document.getElementById("area").value;
        let res = await fetch('/risk?area='+area);
        let data = await res.json();

        let html = "<div class='card'>";
        html += "<h3>Risk Score: <span class='badge'>" + data.risk.toFixed(2) + "</span></h3>";

        html += "<h4>Safe Zones:</h4>";

        data.safe_zones.forEach(function(z){{
            html += "<p>✔ " + z.name + " (Risk: " + z.risk.toFixed(2) + ")</p>";
        }});

        html += "</div>";

        document.getElementById("risk_output").innerHTML = html;

        document.getElementById("crowd_input").innerHTML =
        "<div class='card'><h3>Step 2: Enter Crowd Size</h3>" +
        "<input id='people' placeholder='Enter number of people'>" +
        "<button onclick='distribute()'>Distribute Crowd</button></div>";
    }}


    async function distribute(){{
        let people = document.getElementById("people").value;
        let area = document.getElementById("area").value;

        let res = await fetch('/distribution?area='+area+'&people='+people);
        let data = await res.json();

        let html = "<div class='card'><h3>Crowd Distribution</h3>";

        for(let i=0;i<data.safe_zones.length;i++){{
            html += "<p>➡ " + data.safe_zones[i] + " → " +
                    data.percentage[i] + "% (" +
                    data.people[i] + " people)</p>";
        }}

        html += "<button onclick='routes()'>Generate Routes</button></div>";

        document.getElementById("distribution_output").innerHTML = html;
    }}


    async function routes(){{
        let area = document.getElementById("area").value;

        let res = await fetch('/routes?area='+area);
        let data = await res.json();

        let html = "<div class='card'><h3>Optimized Routes</h3>";

        for(let k in data.routes){{
            html += "<p><b>" + k + "</b><br>" +
                    data.routes[k].join(" → ") + "</p><hr>";
        }}

        html += "</div>";

        document.getElementById("routes_output").innerHTML = html;
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
        {"name": row['area'], "risk": row['risk']}
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
def routes(area:str):
    data = calculate_risk()
    safe = data.tail(3)['area'].values

    routes = {}
    for zone in safe:
        routes[zone] = nx.shortest_path(G, area, zone, weight='weight')

    return {"routes": routes}
