# paste your full app.py code here
from fastapi import FastAPI
import pandas as pd
import numpy as np
import networkx as nx

app = FastAPI()

@app.get("/")
def home():
    return {"message": "AI Disaster Evacuation System Running"}

@app.get("/evacuate")
def evacuate():

    # ---------- LOAD DATA ----------
    areas = pd.read_csv("realistic_100_areas.csv")
    roads = pd.read_csv("realistic_100_roads.csv")

    # ---------- RISK ----------
    areas['risk'] = (
        0.4 * areas['population_density'] +
        0.3 * areas['hazard_level'] +
        0.2 * areas['rainfall']
    )

    # ---------- GRAPH ----------
    G = nx.Graph()
    for _, row in roads.iterrows():
        cost = row['distance'] / row['capacity']
        G.add_edge(row['source'], row['destination'], weight=cost)

    # ---------- SOURCE ----------
    high_risk = areas.sort_values(by='risk', ascending=False)
    source = high_risk.iloc[0]['area']

    # ---------- SAFE ZONES ----------
    safe_zones = high_risk.tail(3)['area'].values
    safe_zones = [z for z in safe_zones if z != source]

    routes = {}
    for zone in safe_zones:
        path = nx.shortest_path(G, source=source, target=zone, weight='weight')
        routes[zone] = path

    return {
        "source": source,
        "safe_zones": safe_zones,
        "routes": routes
    }
