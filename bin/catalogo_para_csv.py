#!/usr/bin/env python3
"""Converte o catalogo JSONL numa planilha de REVISAO HUMANA da taxonomia.

Nao e relatorio: e instrumento de trabalho. As colunas finais sao para Mateus preencher,
e a ordem das linhas foi escolhida para que o que mais precisa de revisao venha primeiro.

Ordem: recuperados na 2a passagem, depois fora_de_escopo confirmado, depois confianca baixa,
depois confianca media, e so entao o resto. Quem parar na metade terá revisado o que importa.
"""
import argparse, csv, io, json, sys

COLS = ["ordem_revisao", "subarea_principal", "subarea_secundaria", "confianca",
        "recuperado_na_2a", "escopo_2a_passagem", "natureza", "ano", "titulo",
        "veiculo", "idioma", "paginas", "status", "arquivo",
        "REVISAO_subarea", "REVISAO_excluir", "REVISAO_nota"]

def prioridade(r):
    if r.get("recuperado_na_2a"):                       return 0
    if r.get("subarea_principal") == "fora_de_escopo":  return 1
    if r.get("status") != "ok":                         return 2
    return {"baixa": 3, "media": 4}.get(r.get("confianca"), 5)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogo", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    regs = [json.loads(l) for l in io.open(a.catalogo, encoding="utf-8") if l.strip()]
    regs.sort(key=lambda r: (prioridade(r), r.get("subarea_principal") or "",
                             r.get("arquivo") or ""))
    with io.open(a.saida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for i, r in enumerate(regs, 1):
            r = dict(r)
            r["ordem_revisao"] = i
            r["autores"] = "; ".join(r.get("autores") or [])
            w.writerow(r)
    n = len(regs)
    pri = [sum(1 for r in regs if prioridade(r) == k) for k in range(6)]
    print("%s  %d linhas" % (a.saida, n))
    print("  recuperados na 2a passagem ... %4d  (revisar primeiro)" % pri[0])
    print("  fora_de_escopo confirmado .... %4d  (confirmar a exclusao um a um)" % pri[1])
    print("  sem texto ou com erro ........ %4d" % pri[2])
    print("  confianca baixa .............. %4d" % pri[3])
    print("  confianca media .............. %4d" % pri[4])
    print("  confianca alta ............... %4d" % pri[5])

if __name__ == "__main__":
    main()
