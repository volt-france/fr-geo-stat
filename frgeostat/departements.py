
import sys
import json
import geopandas as gpd
import pandas as pd
import plotly.express as px
import folium as fl
import numpy as np
import shapely
import requests as rq
from folium.plugins import Search
from frgeostat.utils import cerr, SITE_ROOT, cout
from quickbar import Quickbar
from unidecode import unidecode

from typing import Generator, Any, Dict, Callable        

processString = lambda s : unidecode(s).lower().replace("'", "")

class Departements:
    def __init__(self, save: bool = False) -> None:
        qbar = Quickbar('spin')
        qbar.bar.start()
        starting = qbar.bar.add_task("Downloading Departements Data...", total=None, start=True)
        self.df = pd.read_parquet("https://github.com/volt-france/bureaux-vote/releases/download/v0.0.1/plot.scoring.metadata.table.parquet")
        
        self.df.prob_volt = self.df.prob_volt * 100.0
        
        self.lonLow, self.latLow, self.lonHigh, self.latHigh = (-3.836336, 33.525296, 11.470944, 61.306248)
        # margins:
        self.lonLow, self.latLow, self.lonHigh, self.latHigh = 0.8*self.lonLow, 0.8*self.latLow, 1.1*self.lonHigh, 1.1*self.latHigh
        qbar.bar.remove_task(starting)
        geotask = qbar.bar.add_task("Downloading geometries...", total=None, start=True)
        self.geo = rq.get("https://france-geojson.gregoiredavid.fr/repo/departements.geojson").json()
        qbar.bar.remove_task(geotask)
        mkmap = qbar.bar.add_task("Making Map...", total=None, start=True)
        self.m = fl.Map(
            location=[47, 2.5], zoom_start=6,
            tiles="CartoDB positron", max_bounds=True,
            max_lat=self.latHigh, max_lon=self.lonHigh,
            min_lat=self.latLow, min_lon=self.lonLow, 
            min_zoom=6
            )
        self.perDeptMaps = {}
        qbar.bar.remove_task(mkmap)
        proctask = qbar.bar.add_task("Processing metadata ...", total=None, start=True)
        dropcols = [
            'id', 'nom', 'insee', 'bureau', 'num_bureau',
            'num_circo', 'name_circo', 'num_commune', 'name_commune',
            'code', 'label'
            ]

        self.df = self.df.drop(columns=dropcols)\
                .groupby(['num_dept', 'name_dept'])\
                .agg([
                        np.mean,
                        np.std,
                        *[
                            lambda x : np.quantile(x, q=i/100.0) for i in range(100)
                        ]
                    ])
        self.df.columns = self.df.columns.map(lambda s: '_'.join(map(lambda ss: ss.replace('<lambda_', 'q').replace('>',''), s)))
        self.df = self.df.reset_index()
        if save:
            self.save_data(data=self.df)
        qbar.bar.remove_task(proctask)
        meta = qbar.bar.add_task("Downloading Metadata...", total=None, start=True)
        self.t = rq.get("https://github.com/volt-france/bureaux-vote/releases/download/v0.0.1/translate.json").json()

        self.suffixes = {
            '_median': ' (Median)',
            '_mean': ' (Mean)', 
            '_std': ' (Standard Dev.)',
            **{
                f'_q{i}' : f" ({i}th percentile)" for i in range(100)
            }
            }
        self.T = {
            v+ks  : k+vs for k,v in self.t.items() for ks, vs in self.suffixes.items()
        }
        self.T.update({
            'name_dept' : 'Name of Département'
        })
        self.df = self.df.sort_values("prob_volt_q50")
        self.geometries = []
        self.data = []
        qbar.bar.remove_task(meta)
        qbar.bar.stop()
        

    def describeRow(self, row) -> Generator[str,None, None]:
        for label, code in self.t.items():
            if code in ['code', 'label']:
                continue
            metrics = {
                'IQR': {
                    'UQ': code + '_q75',
                    'LQ': code + '_q25',
                    'MED': code + '_q50',
                    'template': lambda lq, uq, med: f"Median = {round(med,2)} - IQ Interval ({round(lq,2)}, {round(uq,2)}) - IQR {round(uq - lq,2)}"
                },
                'MU+SD': {
                    'MU': code + '_mean',
                    'SD': code + '_std',
                    'template' : lambda mu, sd: f"{round(mu,2)} ± {round(sd if sd else 0.0, 2)} (μ ± σ)"
                },
                'EXTR': {
                    'D10': code+'_q10',
                    'D90': code+'_q90',
                    'template' : lambda low, high: f"Extreme Values: {round(high/low,2)} (D90/D10) - D10 = {round(low,2)} - D90 = {round(high,2)}"
                }
            }
            
            for metric, opts in metrics.items():
                values = [row[opts[key]] for key in opts if key != 'template']
                templated = opts['template'](*values)
                yield code, label, templated
        
    def propSetterGeoJSON(
        self,
        on: str = None,
        data_on: str = None,
        geo_on: str = None,
        popup_on: str = None
        ):
        data = self.df
        geometries = self.geo
        
        if on is not None:
            data_on = geo_on = on
        elif not data_on or not geo_on:
            cerr.log("[bold red]Error: must either specify `on=...` or both `on_data` and `on_geo`[/bold red]")
            sys.exit(1)
        
        is_collection = 'features' in geometries
        if not is_collection:
            geometries = {"type":"FeatureCollection", "features": [geometries]}
            
        idx = 0
        for georow in Quickbar.track(geometries['features'], message="Processing geometries.."):
            
            rows = data[data[data_on].astype(str).str.lower().str.contains(str(georow['properties'][geo_on]).lower())].copy()
            for i, r in rows.iterrows():
                columns = []
                aliases = []
                for col, lab, val in self.describeRow(r):
                    if col not in columns:
                        columns += [col]
                        aliases += [lab]
                    
                    georow['properties'][col] = val
                    props = georow['properties']
                    popup = fl.Popup(f"<a href={SITE_ROOT + f'/#/map/z/dept/{processString(props[geo_on])}'}><h4>Go to Zone</h4></a>") if popup_on else None
                    yield fl.GeoJson(
                        data={"type":"FeatureCollection", "features": [georow]},
                        style_function=lambda x: { 'fillColor' : '#00000000', 'lineColor': '#00000000', 'line_opacity':0.01, "weight": 0.01},
                        tooltip=fl.GeoJsonTooltip(fields=columns, aliases=aliases),
                        popup=popup
                        )
                idx += 1
        return columns, aliases, geometries
        
    def save_data(self, data: pd.DataFrame):
        data.to_parquet("departement.lvl.aggregate.metadata.wide.parquet")
        dfl = data.melt(id_vars=['name_dept', 'num_dept'], value_name='datum', var_name='kind')
        dfl['variable'] = dfl.kind.apply(lambda s: s[:s.rfind('_')])
        dfl['statistic'] = dfl.kind.apply(lambda s: s[s.rfind('_')+1:])
        dfl = dfl.drop(columns='kind')
        dfl.to_parquet("departement.lvl.aggregate.metadata.long.parquet")
                
                
    def transform(self):

        chloro = fl.Choropleth(
            geo_data=self.geo,
            name="choropleth",
            data=self.df,
            columns=["num_dept", "prob_volt_q50"],
            key_on="feature.properties.code",
            fill_color="YlGn",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Probability to vote Volt (%)",
        )

        fg = fl.FeatureGroup(name="tooltips")


        for geolayer in self.propSetterGeoJSON(data_on='name_dept', geo_on='nom', popup_on='name_dept'):
            fg.add_child(geolayer)
        
        
        chloro.add_to(self.m)
        fg.add_to(self.m)
        self.m.keep_in_front(fg)
        fl.LayerControl().add_to(self.m)
        
    def build(self):
        return self.m
    
    def buildDepts(self):
        geodf = gpd.read_file("https://france-geojson.gregoiredavid.fr/repo/departements.geojson")
        deptMaps = {}
        for i, row in Quickbar.track(geodf.iterrows()):
            center = [row.geometry.centroid.x, row.geometry.centroid.y]

            lonLow, latLow, lonHigh, latHigh = row.geometry.bounds

            dm = fl.Map(
                location=center, zoom_start=10,
                tiles="CartoDB positron", max_bounds=True,
                max_lat=latHigh, max_lon=lonHigh,
                min_lat=latLow, min_lon=lonLow, 
                min_zoom=10
                )
            fl.GeoJson(
                data={"type":"FeatureCollection", "features": [json.loads(shapely.to_geojson(row.geometry))] },
                style_function=lambda x: { 'line_opacity':0.01, "weight": 0.01, 'opacity': 0.1},
                ).add_to(dm)
            
            deptMaps[processString(row.nom)] = dm

        return deptMaps
    