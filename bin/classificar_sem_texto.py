#!/home/mateus/env_transporte/bin/python
"""Classifica PROVISORIAMENTE os documentos sem texto extraivel (pendente_ocr, erro_leitura)
usando SO o caminho da pasta e o nome do arquivo, como manda a especificacao de Mateus
(21/11/2026, taxonomia v2, regra 2.4).

Travas por construcao, nao por pedido no prompt:
  - confianca restrita pelo esquema a 'media' ou 'baixa': 'alta' nao e representavel, porque
    classificacao por nome de arquivo nunca e alta.
  - titulo, ano e autor NAO existem no esquema de saida: nao ha como inventa-los.
  - origem_classificacao = 'inferencia_caminho_titulo' e gravada pelo codigo, nao pelo modelo.
Uso: classificar_sem_texto.py --entrada lista.txt --saida sem_texto_v2.jsonl
"""
import argparse, json, os, sys, time
from pathlib import Path
os.environ.setdefault("TAXONOMIA_ACERVO", "subareas_transportes_v2.json")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm
CFG = json.loads((Path(__file__).resolve().parent.parent / "config" / os.environ["TAXONOMIA_ACERVO"]).read_text())
SUB = CFG["subareas"]

# ORDEM DAS PROPRIEDADES E DECISAO DE PROJETO, NAO ESTETICA. Com decodificacao restrita o
# modelo emite as chaves na ordem do esquema. Com 'motivo' por ULTIMO ele escolhia o rotulo
# antes de raciocinar: medido em 21/11/2026, 2 de 3 errados com o motivo CERTO e o rotulo
# errado ("sugere um mapa rodoviario" -> uso_solo_acessibilidade_espacial). Motivo PRIMEIRO.
ESQUEMA = {"type": "object", "properties": {
    "motivo": {"type": "string"},
    "subarea_principal": {"type": "string", "enum": sorted(SUB)},
    "subarea_secundaria": {"type": "array", "items": {"type": "string", "enum": sorted(SUB)}, "maxItems": 2},
    "confianca": {"type": "string", "enum": ["media", "baixa"]}},
    "required": ["motivo", "subarea_principal", "subarea_secundaria", "confianca"]}

PROMPT = """Voce cataloga um acervo tecnico de Engenharia de Transportes. Deste documento NAO foi
possivel extrair texto (PDF digitalizado ou ilegivel). Voce so tem o CAMINHO e o NOME do arquivo.

CAMINHO: {pasta}
ARQUIVO: {nome}

SUBAREAS (chave e descricao):
{subareas}

{regras}

Escreva PRIMEIRO o motivo (o que o nome e a pasta indicam), e SO DEPOIS a subarea principal, ate duas secundarias (somente se o proprio nome ou caminho
indicar DOIS assuntos; na duvida, lista vazia), a confianca e um motivo curto.
REGRA FINAL: confianca 'media' SO quando o nome ou a pasta forem inequivocos (ex.: HCM2010,
DER-SP/Projeto Padrao, Conditional Logit Analysis, DNIT ISF); qualquer ambiguidade e 'baixa'.
A pasta e evidencia forte: '3 - Ferrovias' e '1 - Aeroportos' indicam modos_ferro_aero_hidro."""

def classificar(rel):
    p = Path(rel)
    pasta = str(p.parent) if str(p.parent) != "." else "(raiz do acervo, sem pasta tematica)"
    pedido = PROMPT.format(pasta=pasta, nome=p.name,
                           subareas="\n".join("  %-36s %s" % kv for kv in SUB.items()),
                           regras=CFG.get("regras_finais", ""))
    bruto, _, _ = llm.chamar_local("qwen3:14b", pedido, 8192, 400, 0.1, esquema=ESQUEMA, pensar=False)
    d = json.loads(bruto)
    sec = [s for s in d.get("subarea_secundaria") or [] if s != d["subarea_principal"]]
    return {"arquivo": rel, "subarea_principal": d["subarea_principal"],
            "subarea_secundaria": ";".join(dict.fromkeys(sec))[:200] or None,
            "confianca": d["confianca"], "motivo_inferencia": d.get("motivo", "")[:300],
            "origem_classificacao": "inferencia_caminho_titulo",
            "titulo": None, "ano": None, "autores": []}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--entrada"); ap.add_argument("--saida")
    a = ap.parse_args()
    feitos = set()
    if Path(a.saida).exists():
        feitos = {json.loads(l)["arquivo"] for l in open(a.saida)}
    lista = [l.strip() for l in open(a.entrada) if l.strip() and l.strip() not in feitos]
    t0 = time.time()
    with open(a.saida, "a", encoding="utf-8") as f:
        for i, rel in enumerate(lista, 1):
            try:
                r = classificar(rel)
            except Exception as e:
                r = {"arquivo": rel, "erro": f"{type(e).__name__}: {e}"[:200]}
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
            print(f"{i}/{len(lista)} {time.time()-t0:.0f}s {r.get('subarea_principal','ERRO')} {r.get('confianca','')} | {rel[-70:]}", flush=True)
    print("FIM")
