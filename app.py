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
    return areas.sort_values(by='risk', ascending=False)

# ---------------- SAFE ZONES ----------------
def get_safe_zones(data, area, k=3):
    selected = data[data['area']==area].iloc[0]

    safe = data[
        (data['area'] != area) &
        (data['risk'] < selected['risk'])
    ].nsmallest(k, 'risk')

    return safe['area'].values

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
        cursor:pointer;
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
        <h3>Select Area</h3>
        <select id="area" onchange="resetAll()">{options}</select>
        <button onclick="analyze()">Analyze Risk</button>
    </div>

    <div id="step2"></div>
    <div id="step3"></div>
    <div id="step4"></div>
    <div id="step5"></div>

    <script>

    function resetAll(){{
        document.getElementById("step2").innerHTML="";
        document.getElementById("step3").innerHTML="";
        document.getElementById("step4").innerHTML="";
        document.getElementById("step5").innerHTML="";
    }}

    async function analyze(){{
        resetAll();
        let area = document.getElementById("area").value;

        let data = await (await fetch('/risk?area='+area)).json();

        let html = "<div class='card'>";
        html += "<h3>Risk Score: " + data.risk.toFixed(2) + "</h3>";
        html += "<canvas id='riskChart'></canvas>";

        html += "<input id='people' placeholder='Enter number of people'>";
        html += "<button onclick='distribute()'>Distribute Crowd</button>";
        html += "</div>";

        document.getElementById("step2").innerHTML = html;

        new Chart(document.getElementById("riskChart"), {{
            type:'bar',
            data:{{
                labels:data.safe_zones.map(z=>z.name),
                datasets:[{{data:data.safe_zones.map(z=>z.risk)}}]
            }}
        }});
    }}

    async function distribute(){{
        document.getElementById("step3").innerHTML="";
        document.getElementById("step4").innerHTML="";
        document.getElementById("step5").innerHTML="";

        let area=document.getElementById("area").value;
        let people=document.getElementById("people").value;

        let data=await (await fetch('/distribution?area='+area+'&people='+people)).json();

        let html="<div class='card'>";
        html+="<h3>Crowd Distribution</h3>";
        html+="<canvas id='distChart'></canvas>";

        html+="<input id='k' placeholder='Number of routes'>";
        html+="<button onclick='routes()'>Generate Routes</button>";
        html+="</div>";

        document.getElementById("step3").innerHTML=html;

        new Chart(document.getElementById("distChart"), {{
            type:'bar',
            data:{{
                labels:data.safe_zones,
                datasets:[{{data:data.percentage}}]
            }}
        }});
    }}

    async function routes(){{
        document.getElementById("step4").innerHTML="";
        document.getElementById("step5").innerHTML="";

        let area=document.getElementById("area").value;
        let k=document.getElementById("k").value||3;

        let data=await (await fetch('/routes?area='+area+'&k='+k)).json();

        let html="<div class='card'><h3>All Routes</h3>";

        data.routes.forEach((r,i)=>{{
            html+="<p>Route "+(i+1)+": "+r.join(" → ")+"</p>";
        }});

        html+="<select id='dest'>";
        data.routes.forEach((r,i)=>{{
            html+="<option value='"+i+"'>Destination "+(i+1)+"</option>";
        }});
        html+="</select>";

        html+="<button onclick='bestRoute()'>Show Best Route</button></div>";

        window.routes=data.routes;

        document.getElementById("step4").innerHTML=html;
    }}

    function bestRoute(){{
        let i=document.getElementById("dest").value;

        let html="<div class='card best'>";
        html+="<h3>⭐ Best Route</h3>";
        html+=window.routes[i].join(" → ");
        html+="</div>";

        document.getElementById("step5").innerHTML=html;
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
            {"name": s, "risk": float(data[data['area']==s]['risk'].values[0])}
            for s in safe
        ]
    }

@app.get("/distribution")
def distribution(area:str, people:int):
    data = calculate_risk()
    safe = get_safe_zones(data, area)

    perc, ppl = genetic_distribution(len(safe), int(people))

    return {"safe_zones": list(safe), "percentage": perc, "people": ppl}

@app.get("/routes")
def routes(area:str, k:int=3):
    data = calculate_risk()
    safe = get_safe_zones(data, area, k)

    all_paths=[]

    for zone in safe:
        path=nx.dijkstra_path(G, area, zone, weight='weight')
        cost=nx.path_weight(G, path, weight='weight')
        all_paths.append((cost,path))

    all_paths.sort(key=lambda x:x[0])

    return {"routes":[p[1] for p in all_paths]}
