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

    areas['risk'] = 10 + 90 * (raw_risk - raw_risk.min()) / (raw_risk.max() - raw_risk.min())
    return areas

# ---------------- SAFE ZONES (FINAL FIX) ----------------
def get_safe_zones(data, area, k=3):
    selected = data[data['area']==area].iloc[0]

    # 🔥 relative filtering
    candidates = data[
        (data['area'] != area) &
        (data['risk'] < selected['risk'])
    ]

    # 🔥 if too few → fallback
    if len(candidates) < k:
        candidates = data[data['area'] != area]

    # 🔥 take top 15 safest (not just 3)
    top = candidates.nsmallest(min(15, len(candidates)), 'risk')

    # 🔥 sample from them → dynamic result
    safe = top.sample(k)

    return safe

# ---------------- GA ----------------
def genetic_distribution(n, total_people):
    vals = np.random.dirichlet(np.ones(n))
    perc = [round(v*100,2) for v in vals]
    ppl = [int(v*total_people) for v in vals]
    return perc, ppl

# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard():

    options = "<option value='' disabled selected>Select Area</option>" + \
              "".join([f"<option value='{a}'>{a}</option>" for a in areas['area']])

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
    margin-top:10px;
    border-radius:6px;
}}
</style>
</head>

<body>

<h1>🚨 RescueNet</h1>

<div class="card">
    <select id="area" onchange="resetAll()">{options}</select>
    <button onclick="analyze()">Analyze Risk</button>
</div>

<div id="step2"></div>
<div id="step3"></div>
<div id="step4"></div>
<div id="step5"></div>

<script>

function resetAll(){{
    step2.innerHTML="";
    step3.innerHTML="";
    step4.innerHTML="";
    step5.innerHTML="";
}}

async function analyze(){{
    resetAll();

    let area = document.getElementById("area").value;
    if(!area) return alert("Select area");

    let data = await (await fetch('/risk?area='+area)).json();

    let html = "<div class='card'>";
    html += "<h3>Risk Score: "+data.risk.toFixed(2)+"</h3>";

    html += "<h4>Safe Zones:</h4>";
    data.safe_zones.forEach(z=>{{
        html += "<p>"+z.name+" → "+z.risk.toFixed(2)+"</p>";
    }});

    html += "<canvas id='riskChart'></canvas>";

    html += "<input id='people' placeholder='Enter people'>";
    html += "<button onclick='distribute()'>Next</button></div>";

    step2.innerHTML = html;

    new Chart(document.getElementById("riskChart"), {{
        type:'bar',
        data:{{
            labels:data.safe_zones.map(z=>z.name),
            datasets:[{{label:'Risk',data:data.safe_zones.map(z=>z.risk)}}]
        }}
    }});

    window.safeZones = data.safe_zones.map(z=>z.name);
}}

async function distribute(){{
    step3.innerHTML=""; step4.innerHTML=""; step5.innerHTML="";

    let people = document.getElementById("people").value;
    if(!people) return alert("Enter people");

    let zones = window.safeZones.join(",");

    let data = await (await fetch(`/distribution?people=${{people}}&zones=${{zones}}`)).json();

    let html = "<div class='card'>";
    html += "<h3>Crowd Distribution</h3>";

    for(let i=0;i<data.safe_zones.length;i++){{
        html += "<p>"+data.safe_zones[i]+" → "+data.percentage[i]+"%</p>";
    }}

    html += "<canvas id='distChart'></canvas>";

    html += "<select id='destination'>";
    html += "<option disabled selected>Select Destination</option>";
    data.safe_zones.forEach(z=>{{
        html += "<option value='"+z+"'>"+z+"</option>";
    }});
    html += "</select>";

    html += "<input id='k' placeholder='Number of routes'>";
    html += "<button onclick='routes()'>Generate Routes</button></div>";

    step3.innerHTML = html;

    new Chart(document.getElementById("distChart"), {{
        type:'bar',
        data:{{
            labels:data.safe_zones,
            datasets:[{{label:'People %',data:data.percentage}}]
        }}
    }});
}}

async function routes(){{
    step4.innerHTML=""; step5.innerHTML="";

    let area = document.getElementById("area").value;
    let dest = document.getElementById("destination").value;
    let k = document.getElementById("k").value || 3;

    if(!dest) return alert("Select destination");

    let data = await (await fetch(`/routes?area=${{area}}&destination=${{dest}}&k=${{k}}`)).json();

    let html = "<div class='card'><h3>Routes</h3>";

    data.routes.forEach((r,i)=>{{
        html += "<p>Route "+(i+1)+": "+r.join(" → ")+"</p>";
    }});

    html += "<button onclick='bestRoute()'>Best Route</button></div>";

    window.best = data.best;

    step4.innerHTML = html;
}}

function bestRoute(){{
    step5.innerHTML = "<div class='card best'><h3>⭐ Best Route</h3>"+window.best.join(" → ")+"</div>";
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
    safe = get_safe_zones(data, area)

    return {
        "risk": float(selected['risk']),
        "safe_zones": [
            {"name": r['area'], "risk": float(r['risk'])}
            for _, r in safe.iterrows()
        ]
    }

@app.get("/distribution")
def distribution(people:int, zones:str):
    safe = zones.split(",")

    perc, ppl = genetic_distribution(len(safe), int(people))

    return {"safe_zones": safe, "percentage": perc, "people": ppl}

@app.get("/routes")
def routes(area:str, destination:str, k:int=3):
    paths = nx.shortest_simple_paths(G, area, destination, weight='weight')

    routes = []
    for i, path in enumerate(paths):
        routes.append(path)
        if i == k-1:
            break

    return {"routes": routes, "best": routes[0]}
