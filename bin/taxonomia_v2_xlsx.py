#!/home/mateus/env_transporte/bin/python
"""Planilha de revisao da taxonomia v2. Resumo e desmembramento sao FORMULAS sobre a aba
'revisao': corrigir uma classe la recalcula as contagens. Uso: taxonomia_v2_xlsx.py entrada.json saida.xlsx"""
import json, sys
from collections import Counter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
ent, sai = sys.argv[1], sys.argv[2]
D = json.load(open(ent)); COLS, LIN = D["cols"], D["linhas"]
TAX = json.load(open("/home/mateus/ecossistema/config/subareas_transportes_v2.json")); SUB = TAX["subareas"]
for a in SUB:   # COUNTIF com curinga na secundaria exige que nenhuma chave contenha outra
    assert not any(a != b and a in b for b in SUB), f"chave {a} contida em outra: curinga contaria errado"
C = {c: L(i + 1) for i, c in enumerate(COLS)}; N = len(LIN) + 1
F = "Arial"; fh = Font(name=F, bold=True, color="FFFFFF"); fn = Font(name=F, size=10); fb = Font(name=F, bold=True, size=10)
azul = PatternFill("solid", fgColor="1F4E78"); amarelo = PatternFill("solid", fgColor="FFF2CC"); cinza = PatternFill("solid", fgColor="F2F2F2")
wb = Workbook()

# ---------------- revisao
ws = wb.active; ws.title = "revisao"
ws.append(COLS)
for o in LIN: ws.append([o.get(c, "") for c in COLS])
for c in ws[1]: c.font, c.fill, c.alignment = fh, azul, Alignment(wrap_text=True, vertical="center")
for row in ws.iter_rows(min_row=2):
    for c in row: c.font = fn
larg = {"ordem_revisao": 8, "arquivo": 48, "titulo": 50, "autores": 22, "ano": 6, "veiculo": 22, "idioma": 6,
        "natureza": 14, "paginas": 7, "status": 12, "subarea_principal": 30, "subarea_secundaria": 34,
        "confianca": 9, "origem_classificacao": 22, "ajuste": 50, "subarea_v1": 20, "recuperado_na_2a_v1": 10,
        "motivo_secundaria": 40, "duplicata": 14, "duplicata_tipo": 10, "duplicata_canonico": 40,
        "REVISAO_subarea": 30, "REVISAO_excluir": 10, "REVISAO_nota": 40}
for c in COLS: ws.column_dimensions[C[c]].width = larg.get(c, 14)
for c in ("REVISAO_subarea", "REVISAO_excluir", "REVISAO_nota"):
    for r in range(2, N + 1): ws[f"{C[c]}{r}"].fill = amarelo
ws.freeze_panes = "C2"; ws.auto_filter.ref = f"A1:{C[COLS[-1]]}{N}"
dv = DataValidation(type="list", formula1=f"=taxonomia!$A$2:$A${len(SUB)+1}", allow_blank=True)
dv.error = "Use uma das 22 chaves da aba taxonomia."; ws.add_data_validation(dv); dv.add(f"{C['REVISAO_subarea']}2:{C['REVISAO_subarea']}{N}")
dv2 = DataValidation(type="list", formula1='"sim,nao"', allow_blank=True); ws.add_data_validation(dv2)
dv2.add(f"{C['REVISAO_excluir']}2:{C['REVISAO_excluir']}{N}")
ws[f"{C['REVISAO_subarea']}1"].comment = Comment("PREENCHER AQUI. Lista suspensa com as 22 chaves. O valor vence qualquer classificacao de modelo na proxima geracao.", "Claude")
ws[f"{C['origem_classificacao']}1"].comment = Comment("modelo_texto_v2 | inferencia_caminho_titulo | correcao_dirigida | regra_pasta_especificacao | revisao_manual | pendente. Ver aba leia_me.", "Claude")

# ---------------- taxonomia
wt = wb.create_sheet("taxonomia"); wt.append(["chave", "descricao (especificacao de 21/11/2026, com a correcao de ferrovia registrada no leia_me)"])
for k, v in SUB.items(): wt.append([k, v])
for c in wt[1]: c.font, c.fill = fh, azul
for row in wt.iter_rows(min_row=2):
    for c in row: c.font, c.alignment = fn, Alignment(wrap_text=True, vertical="top")
wt.column_dimensions["A"].width = 36; wt.column_dimensions["B"].width = 120

# ---------------- resumo (formulas)
wr = wb.create_sheet("resumo", 1)
P, S, O = C["subarea_principal"], C["subarea_secundaria"], C["origem_classificacao"]
wr.append(["subarea", "como principal", "% do classificado", "como secundaria"])
for c in wr[1]: c.font, c.fill = fh, azul
for i, k in enumerate(SUB, start=2):
    wr.append([k, f"=COUNTIF(revisao!${P}$2:${P}${N},A{i})", f"=IF($B${len(SUB)+2}=0,0,B{i}/$B${len(SUB)+2})",
               f'=COUNTIF(revisao!${S}$2:${S}${N},"*"&A{i}&"*")'])
t = len(SUB) + 2
wr.append(["TOTAL classificado", f"=SUM(B2:B{t-1})", f"=SUM(C2:C{t-1})", f"=SUM(D2:D{t-1})"])
wr.append(["conferencia: linhas com classe na aba revisao", f'=COUNTIF(revisao!${P}$2:${P}${N},"?*")',
           f'=IF(B{t+1}=B{t},"OK","DIVERGE")', ""])
for r in range(2, t + 2): wr[f"C{r}"].number_format = "0.0%"
wr[f"C{t+1}"].number_format = "General"
r0 = t + 4; wr.cell(r0, 1, "origem_classificacao").font = fh; wr.cell(r0, 1).fill = azul; wr.cell(r0, 2, "linhas").font = fh; wr.cell(r0, 2).fill = azul
for j, og in enumerate(["modelo_texto_v2", "inferencia_caminho_titulo", "correcao_dirigida",
                        "regra_pasta_especificacao", "revisao_manual", "pendente"], start=r0 + 1):
    wr.cell(j, 1, og); wr.cell(j, 2, f"=COUNTIF(revisao!${O}$2:${O}${N},A{j})")
r1 = r0 + 8; Dp = C["duplicata"]
wr.cell(r1, 1, "duplicatas").font = fh; wr.cell(r1, 1).fill = azul; wr.cell(r1, 2, "linhas").font = fh; wr.cell(r1, 2).fill = azul
for j, dp in enumerate(["canonico", "duplicata_raiz", "duplicata"], start=r1 + 1):
    wr.cell(j, 1, dp); wr.cell(j, 2, f"=COUNTIF(revisao!${Dp}$2:${Dp}${N},A{j})")
for row in wr.iter_rows(min_row=2):
    for c in row:
        if c.font != fh: c.font = fn
wr.column_dimensions["A"].width = 44
for x in "BCD": wr.column_dimensions[x].width = 18

# ---------------- desmembramento v1 -> v2 (formulas)
wd = wb.create_sheet("desmembramento_v1", 2)
V1 = [k for k, _ in Counter(o["subarea_v1"] for o in LIN if o["subarea_v1"]).most_common()]
V1c = C["subarea_v1"]
wd.append(["subarea v2  \\  subarea v1"] + V1)
for c in wd[1]: c.font, c.fill, c.alignment = fh, azul, Alignment(wrap_text=True)
for i, k in enumerate(SUB, start=2):
    wd.append([k] + [f"=COUNTIFS(revisao!${V1c}$2:${V1c}${N},{L(j+2)}$1,revisao!${P}$2:${P}${N},$A{i})" for j in range(len(V1))])
tt = len(SUB) + 2
wd.append(["TOTAL"] + [f"=SUM({L(j+2)}2:{L(j+2)}{tt-1})" for j in range(len(V1))])
wd.append(["total da v1 nesta classe"] + [f"=COUNTIF(revisao!${V1c}$2:${V1c}${N},{L(j+2)}$1)" for j in range(len(V1))])
for row in wd.iter_rows(min_row=2):
    for c in row: c.font = fn
for r in (tt, tt + 1):
    for c in wd[r]: c.font = fb
if "demanda_escolha" in V1:
    col = L(V1.index("demanda_escolha") + 2)
    for r in range(1, tt + 2): wd[f"{col}{r}"].fill = amarelo
    wd[f"{col}1"].comment = Comment("Os 651 que a especificacao manda desmembrar nas 5 classes de demanda.", "Claude")
wd.column_dimensions["A"].width = 36
for j in range(len(V1)): wd.column_dimensions[L(j + 2)].width = 14
wd.freeze_panes = "B2"

# ---------------- listas de apoio (copias estaticas, rotuladas como tal)
def lista(nome, filtro, cols, nota):
    w = wb.create_sheet(nome); w.append([nota]); w["A1"].font = Font(name=F, italic=True, size=9)
    w.append(cols)
    for c in w[2]: c.font, c.fill = fh, azul
    for o in sorted(filter(filtro, LIN), key=lambda o: (o.get("duplicata_canonico") or o["arquivo"], o["arquivo"])):
        w.append([o.get(c, "") for c in cols])
    for row in w.iter_rows(min_row=3):
        for c in row: c.font = fn
    for i, c in enumerate(cols, 1): w.column_dimensions[L(i)].width = larg.get(c, 14)
    w.freeze_panes = "A3"
lista("os_53_recuperados", lambda o: o["recuperado_na_2a_v1"] == "sim",
      ["arquivo", "titulo", "subarea_v1", "subarea_principal", "subarea_secundaria", "confianca", "origem_classificacao", "ajuste"],
      "Copia estatica dos 53 que a v1 recuperou na 2a passagem, reavaliados na v2. Corrigir na aba revisao, nao aqui.")
lista("duplicatas", lambda o: bool(o["duplicata"]),
      ["arquivo", "duplicata", "duplicata_tipo", "duplicata_canonico", "paginas", "subarea_principal"],
      "Copia estatica. exata = sha256 identico; provavel = mesmo nome normalizado e mesmo numero de paginas, conteudo diferente.")
lista("sem_texto", lambda o: o["origem_classificacao"] in ("inferencia_caminho_titulo", "pendente"),
      ["arquivo", "status", "subarea_principal", "subarea_secundaria", "confianca", "ajuste"],
      "Copia estatica. Classe PROVISORIA por caminho e nome; titulo, ano e autor nao foram inventados.")
wb.move_sheet("taxonomia", offset=len(wb.sheetnames))
wb.save(sai); print("gravado", sai, "abas:", wb.sheetnames)
