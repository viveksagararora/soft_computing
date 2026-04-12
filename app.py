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

# ---------------- RISK ----------------
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
    ppl = [int(v*total_people) for v in vals]
    return perc, ppl


# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def dashboard():

    options = "".join([f"<option value='{a}'>{a}</option>" for a in areas['area']])

    return f"""
    <html>
    <head>
    <title>AI Evacuation Dashboard</title>

    <!-- Leaflet Map -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

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

    #map {{
        height:400px;
        margin-top:20px;
        border-radius:10px;
    }}
    </style>

    </head>

    <body>

    <h1>🚨 AI Disaster Evacuation System</h1>

    <!-- STEP 1 -->
    <div class="card">
    <h3>Select Risk Area</h3>
    <select id="area">{options}</select>
    <button onclick="analyze()">Analyze Risk</button>
    </div>

    <div id="risk_output"></div>
    <div id="crowd_input"></div>
    <div id="distribution_output"></div>
    <div id="routes_output"></div>

    <div id="map"></div>

    <script>

    let map = L.map('map').setView([28.6, 77.2], 11);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {{
        attribution: 'Map data © OpenStreetMap contributors'
    }}).addTo(map);


    async function analyze(){{
        let area = document.getElementById("area").value;

        let res = await fetch('/risk?area='+area);
        let data = await res.json();

        let html = "<div class='card'>";
        html += "<h3>Risk Score: " + data.risk.toFixed(2) + "</h3>";
        html += "<h4>Safe Zones:</h4>";

        data.safe_zones.forEach(function(z){{
            html += "<p>" + z.name + " (Risk: " + z.risk.toFixed(2) + ")</p>";
        }});

        html += "</div>";

        document.getElementById("risk_output").innerHTML = html;

        document.getElementById("crowd_input").innerHTML =
        "<div class='card'><h3>Enter Crowd Size</h3>" +
        "<input id='people' placeholder='Number of people'>" +
        "<button onclick='distribute()'>Distribute</button></div>";
    }}


    async function distribute(){{
        let people = document.getElementById("people").value;
        let area = document.getElementById("area").value;

        let res = await fetch('/distribution?area='+area+'&people='+people);
        let data = await res.json();

        let html = "<div class='card'><h3>Crowd Distribution</h3>";

        for(let i=0;i<data.safe_zones.length;i++){{
            html += "<p>" + data.safe_zones[i] + " → " +
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

        let html = "<div class='card'><h3>Routes</h3>";

        map.eachLayer(layer => {{
            if(layer instanceof L.Marker || layer instanceof L.Polyline)
                map.removeLayer(layer);
        }});

        for(let k in data.routes){{
            html += "<p><b>" + k + "</b>: " +
                    data.routes[k].join(" → ") + "</p>";

            let coords = [];

            data.routes[k].forEach(function(loc){{
                fetch('/coords?area='+loc)
                .then(r => r.json())
                .then(c => {{
                    let latlng = [c.lat, c.lon];
                    coords.push(latlng);
                    L.marker(latlng).addTo(map).bindPopup(loc);

                    if(coords.length > 1){{
                        L.polyline(coords, {{color:'blue'}}).addTo(map);
                    }}
                }});
            }});
        }}

        html += "</div>";

        document.getElementById("routes_output").innerHTML = html;
    }}

    </script>

    </body>
    </html>
    """


# ---------------- API ----------------

@app.get("/risk")
def risk(area:str):
    data = calculate_risk()
    selected = data[data['area']==area].iloc[0]
    safe = data.tail(3)

    safe_zones = [
        {"name": row['area'], "risk": row['risk']}
        for _, row in safe.iterrows()
    ]

    return {"risk": selected['risk'], "safe_zones": safe_zones}


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


@app.get("/coords")
def coords(area:str):
    row = areas[areas['area']==area].iloc[0]
    return {"lat": row['latitude'], "lon": row['longitude']}
