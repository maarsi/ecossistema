"""Teste de viabilidade do Overture Maps (release 2026-11-18.0) para Salvador.
Autorizado por Mateus em 22/11/2026 (bloco II, proposta b). Mede: tempo de consulta remota, contagem
de POI por categoria principal e de edificacoes no recorte, e grava parquet local para uso posterior.
Licencas (docs.overturemaps.org, lidas em 22/11): places CDLA-Permissive-2.0 / Apache-2.0 / CC0 por fonte;
buildings ODbL ("(c) OpenStreetMap contributors, Overture Maps Foundation")."""
import duckdb, time, sys
REL = "2026-11-18.0"; B = (-38.70, -13.02, -38.30, -12.75)   # xmin, ymin, xmax, ymax (Salvador, aprox.)
OUT = "/mnt/nvme_lexar/datasets_sig/overture"
import os; os.makedirs(OUT, exist_ok=True)
con = duckdb.connect()
for e in ("httpfs", "spatial"): con.execute(f"INSTALL {e}; LOAD {e};")
con.execute("SET s3_region='us-west-2';")
filtro = f"bbox.xmin > {B[0]} AND bbox.xmax < {B[2]} AND bbox.ymin > {B[1]} AND bbox.ymax < {B[3]}"
for tema, tipo in (("places", "place"), ("buildings", "building")):
    t = time.time()
    url = f"s3://overturemaps-us-west-2/release/{REL}/theme={tema}/type={tipo}/*"
    con.execute(f"COPY (SELECT * FROM read_parquet('{url}', filename=true, hive_partitioning=1) WHERE {filtro}) "
                f"TO '{OUT}/salvador_{tema}_{REL}.parquet' (FORMAT parquet)")
    n = con.execute(f"SELECT count(*) FROM '{OUT}/salvador_{tema}_{REL}.parquet'").fetchone()[0]
    print(f"{tema}: {n} feicoes em {time.time()-t:.0f} s", flush=True)
print("--- POI por categoria principal (15 maiores)")
for r in con.execute(f"""SELECT categories.primary AS cat, count(*) n FROM '{OUT}/salvador_places_{REL}.parquet'
                        GROUP BY 1 ORDER BY 2 DESC LIMIT 15""").fetchall(): print(r)
print("--- confianca dos POI (quartis)")
print(con.execute(f"SELECT quantile_cont(confidence,[0.25,0.5,0.75]) FROM '{OUT}/salvador_places_{REL}.parquet'").fetchone())
print("--- edificacoes: area total (km2, aprox. por graus->m na latitude) e % com altura")
print(con.execute(f"""SELECT sum(ST_Area(ST_Transform(geometry,'EPSG:4326','EPSG:31984', always_xy:=true)))/1e6,
       avg((height IS NOT NULL)::INT) FROM '{OUT}/salvador_buildings_{REL}.parquet'""").fetchone())
print("FIM")
