import datetime, os, time
import pandas as pd, geopandas as gpd
from shapely.geometry import Point
import r5py
B = os.path.expanduser("~/r5_salvador")
p = pd.read_csv(os.path.join(B, "pontos_200.csv"), dtype={"id": str})
g = gpd.GeoDataFrame({"id": p["id"]},
    geometry=[Point(x, y) for x, y in zip(p["lon"], p["lat"])], crs="EPSG:4326")
rede = r5py.TransportNetwork(os.path.join(B, "dir_r5r", "salvador.osm.pbf"),
    [os.path.join(B, "dir_r5r", "brt.zip"), os.path.join(B, "dir_r5r", "plataforma.zip")])
print("=== tempo, tres repeticoes com max_public_transport_rides=8 ===", flush=True)
for i in range(3):
    t0 = time.time()
    m = r5py.TravelTimeMatrix(rede, origins=g, destinations=g,
        departure=datetime.datetime(2025, 11, 11, 7, 0),
        departure_time_window=datetime.timedelta(minutes=60), percentiles=[50],
        transport_modes=[r5py.TransportMode.TRANSIT, r5py.TransportMode.WALK],
        access_modes=[r5py.TransportMode.WALK], egress_modes=[r5py.TransportMode.WALK],
        max_time=datetime.timedelta(minutes=300), speed_walking=3.6,
        max_public_transport_rides=8)
    print("  repeticao %d: %.1f s" % (i + 1, time.time() - t0), flush=True)
col = "travel_time" if "travel_time" in m.columns else m.columns[-1]
m.rename(columns={col: "t_py"})[["from_id", "to_id", "t_py"]].to_csv(
    os.path.join(B, "matriz_r5py_8.csv"), index=False)
print("gravado", flush=True)
