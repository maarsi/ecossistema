"""Fase 0: renderiza as 58 paginas uma unica vez. Todos os bracos de imagem usam estas."""
import pymupdf, pathlib, hashlib
B = pathlib.Path.home()/"ecossistema/bench"
PDF = B/"dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf"
assert hashlib.sha256(PDF.read_bytes()).hexdigest() == "c19be5398997a7ae18117ac9cdd48ee866757a293652e5f4b26f7e689368649c", "CORPUS DIVERGENTE"
D = B/"derpr/paginas"; D.mkdir(parents=True, exist_ok=True)
d = pymupdf.open(str(PDF))
assert len(d) == 58, f"esperava 58 paginas, achei {len(d)}"
n = 0
for i in range(58):
    f = D/f"p{i+1:02d}.png"
    if not f.exists():
        d[i].get_pixmap(dpi=180).save(str(f)); n += 1
print(f"  58 paginas; renderizadas agora: {n}")
