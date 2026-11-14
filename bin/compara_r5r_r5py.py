# -*- coding: utf-8 -*-
"""Os dois motores devolvem o mesmo tempo? R5 v7.5.1 (r5py) contra v7.6 (r5r),
mesmos 200 pontos, mesma data, mesma janela, mesmo percentil."""
import os
import pandas as pd
B = os.path.expanduser("~/r5_salvador")
py = pd.read_csv(os.path.join(B, "matriz_r5py_8.csv"), dtype={"from_id": str, "to_id": str})
r = pd.read_csv(os.path.join(B, "matriz_r5r_8.csv"), dtype={"from_id": str, "to_id": str})
r = r.rename(columns={"travel_time_p50": "t_r"})
print("pares r5py: %d   pares r5r: %d" % (len(py), len(r)))
m = py.merge(r, on=["from_id", "to_id"], how="outer", indicator=True)
print("cruzamento: %s" % m["_merge"].value_counts().to_dict())
m = m[m["_merge"] == "both"].copy()
amb = m.dropna(subset=["t_py", "t_r"])
print("")
print("pares com valor nos DOIS: %d" % len(amb))
print("so no r5py (r5r nao achou): %d" % int(m["t_r"].isna().sum()))
print("so no r5r  (r5py nao achou): %d" % int(m["t_py"].isna().sum()))
if len(amb):
    d = amb["t_r"] - amb["t_py"]
    print("")
    print("DIFERENCA r5r menos r5py, em minutos:")
    print("  identicos .......... %d de %d  (%.1f%%)"
          % ((d == 0).sum(), len(d), 100.0 * (d == 0).mean()))
    print("  dentro de 1 min .... %d  (%.1f%%)"
          % ((d.abs() <= 1).sum(), 100.0 * (d.abs() <= 1).mean()))
    print("  mediana %+.2f   media %+.3f   desvio %.2f" % (d.median(), d.mean(), d.std()))
    print("  minimo %+.0f   maximo %+.0f" % (d.min(), d.max()))
    print("")
    print("  distribuicao da diferenca:")
    print(d.value_counts().sort_index().head(12).to_string())
