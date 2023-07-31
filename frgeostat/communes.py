import geopandas as gpd
import pandas as pd
import folium as fl
import requests as rq
import json
from quickbar import Quickbar
from bs4 import BeautifulSoup

class Communes:
    def __init__(self) -> None:
        qbar = Quickbar('spin')
        qbar.bar.start()
        starting = qbar.bar.add_task("Downloading Communes Data...", total=None, start=True)
        self.codf = gpd.read_file("https://github.com/volt-france/bureaux-vote/releases/download/v0.0.1/commune.lvl.aggregates.metadata.geojson.zip")
        
        self.codf.prob_volt_mean =  self.codf.prob_volt_mean * 100
        self.codf.prob_volt_std =  self.codf.prob_volt_std * 100
        self.codf.prob_volt_median =  self.codf.prob_volt_median * 100
        self.lonLow, self.latLow, self.lonHigh, self.latHigh = gpd.GeoSeries(self.codf.geometry).unary_union.bounds
        # margins:
        self.lonLow, self.latLow, self.lonHigh, self.latHigh = 0.8*self.lonLow, 0.8*self.latLow, 1.1*self.lonHigh, 1.1*self.latHigh
        qbar.bar.remove_task(starting)
        mkmap = qbar.bar.add_task("Making Map...", total=None, start=True)
        self.m = fl.Map(
            location=[47, 2.5], zoom_start=6,
            tiles="CartoDB positron", max_bounds=True,
            max_lat=self.latHigh, max_lon=self.lonHigh,
            min_lat=self.latLow, min_lon=self.lonLow, 
            min_zoom=6
            )
        qbar.bar.remove_task(mkmap)
        meta = qbar.bar.add_task("Downloading Metadata...", total=None, start=True)
        self.t = rq.get("https://github.com/volt-france/bureaux-vote/releases/download/v0.0.1/translate.json").json()

        self.suffixes = {'_median': ' (Median)','_mean': ' (Mean)', '_std': ' (Standard Dev.)' }
        self.T = {
            v+ks  : k+vs for k,v in self.t.items() for ks, vs in self.suffixes.items()
        }
        self.T.update({
            'nom' : 'Name of Commune',
            'name_dept' : 'Name of Département'
        })
        
        self.geometries = []
        self.data = []
        qbar.bar.remove_task(meta)
        qbar.bar.stop()
        
        
    def transform(self):

        dropcols = [ 'id', 'num_circo_mean', 'num_circo_std',
            'num_circo_median', 'num_commune_mean', 'num_commune_std',
            'num_commune_median', 'geometry'
            ]
        datarows = []
        georows = []
        udf = self.codf[['nom', 'name_dept']].drop_duplicates()
        
        for i, row in Quickbar.track(list(udf.iterrows())):
            rowgeom = gpd.GeoSeries(self.codf[self.codf.nom == row.nom].geometry).unary_union.simplify(tolerance=0.001).__geo_interface__

            rgeo = {
                    "type": "Feature", "id":i, "properties" : { 'nom': row.nom, 'departement': row.name_dept }, "geometry": rowgeom
            }
            georows += [
                    rgeo
            ]
            rowagg = self.codf[self.codf.nom == row.nom].drop(columns=dropcols+['nom', 'name_dept']).median()
            datarows += [{
                    'id': i , 'nom': row.nom, 'departement': row.name_dept, **rowagg.to_dict()
            }]
            
        
        self.data = pd.DataFrame.from_records(datarows)
        self.geometries = {"type":"FeatureCollection", "features": georows}
        
        
    def build(self):
        fl.Choropleth(
            geo_data=self.geometries,
            name="choropleth",
            data=self.data,
            columns=["id", "prob_volt_median"],
            key_on="feature.id",
            fill_color="YlGn",
            fill_opacity=0.7,
            line_opacity=0.15,
            legend_name="Probability to vote Volt (%)",
        ).add_to(self.m)
        
        return self.m
    
    