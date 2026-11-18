#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""catalogar_acervo.py - catalogo do acervo documental, uma linha por documento.

  catalogar_acervo.py --raiz "D:\\40 - REFERENCIAS" --saida ~/base_conhecimento/catalogo.jsonl
  catalogar_acervo.py ... --piloto 60      amostra com semente fixa, para medir antes de rodar tudo
  catalogar_acervo.py ... --retomar        pula documentos ja catalogados na saida

POR QUE EXISTE: indice semantico sem metadado responde mas nao e citavel, e em consultoria a
citacao e o produto. Este script le as primeiras paginas de cada documento e extrai titulo,
autores, ano, veiculo, natureza e subarea, de modo que a busca aceite filtro e devolva citacao.

SO LE o acervo. Nao move, nao renomeia, nao apaga. A saida e um arquivo novo, em outra pasta.
Incremental por sha256: documento inalterado nao e reprocessado.
"""
import argparse, hashlib, json, os, random, re, sys, time
from pathlib import Path

RAIZ_ECO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_ECO / "bin"))
import llm  # noqa: E402

CFG = json.loads((RAIZ_ECO / "config" / "subareas_transportes.json").read_text(encoding="utf-8"))
SUB, NAT = CFG["subareas"], CFG["naturezas"]
PAG_INICIO, MAX_CHARS = 3, 6000

# ESQUEMA JSON. Com ele o Ollama decodifica restrito e a saida e valida por construcao.
# MEDIDO em 17/11/2026: sem esquema, 17,6 s de mediana e 0 de 6 documentos com JSON valido,
# porque o modelo gastava o orcamento de tokens pensando e sobrava resposta vazia. Com
# esquema, 3,0 s e 6 de 6 validos. O enum fecha as chaves de natureza e de subarea, de modo
# que valor fora da taxonomia deixa de ser possivel em vez de ser saneado depois.
ESQUEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "autores": {"type": "array", "items": {"type": "string"}},
        "ano": {"type": ["integer", "null"]},
        "veiculo": {"type": ["string", "null"]},
        "idioma": {"type": "string"},
        "natureza": {"type": "string", "enum": list(NAT)},
        "subarea_principal": {"type": "string", "enum": list(SUB)},
        "subarea_secundaria": {"type": ["string", "null"], "enum": list(SUB) + [None]},
        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
    },
    "required": ["titulo", "autores", "ano", "veiculo", "idioma", "natureza",
                 "subarea_principal", "confianca"],
}


def caminho_ubuntu(c):
    c = c.replace("\\", "/")
    return "/media/mateus/DADOS_01/" + c[3:] if c.lower().startswith("d:/") else c


def hash24(p):
    """Digital de MUDANCA, nao de integridade: tamanho + primeiro e ultimo MB.

    POR QUE NAO O ARQUIVO INTEIRO: o acervo tem 11,4 GB num volume lento, e hashear tudo
    faz o processo ficar preso em E/S com a GPU ociosa. Medido em 18/11: com hash completo
    o catalogo rodava a 11 s/documento com a GPU em 0% e o processo em estado D; o custo
    estava no disco, nao no modelo. Para detectar que um documento mudou, tamanho mais as
    bordas bastam, e leem 2 MB em vez de ate 1 GB.
    NAO usar esta funcao para atestar integridade de arquivo: para isso, sha256 completo."""
    tam = os.path.getsize(p)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read(1 << 20))
        if tam > (2 << 20):
            f.seek(-(1 << 20), os.SEEK_END)
            h.update(f.read(1 << 20))
    h.update(str(tam).encode())
    return h.hexdigest()[:24]


def primeiras_paginas(p):
    """Texto das primeiras paginas e numero total. Devolve ("", n) se nao houver texto."""
    import pymupdf
    with pymupdf.open(p) as d:
        n = d.page_count
        txt = "\n".join(d.load_page(i).get_text("text")
                        for i in range(min(PAG_INICIO, n)))
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt[:MAX_CHARS], n


PROMPT = """Voce cataloga um acervo tecnico de Engenharia de Transportes. Leia o inicio do
documento e devolva APENAS um objeto JSON, sem comentario e sem texto antes ou depois.

Campos:
  titulo               titulo real do documento, nao o nome do arquivo
  autores              lista de autores; lista vazia se nao houver
  ano                  ano de publicacao como numero inteiro; null se nao estiver no texto
  veiculo              periodico, congresso, editora ou orgao emissor; null se nao houver
  idioma               "pt", "en", "es" ou outro codigo de duas letras
  natureza             uma das chaves listadas em NATUREZAS
  subarea_principal    uma das chaves listadas em SUBAREAS
  subarea_secundaria   outra chave de SUBAREAS, ou null se nao couber
  confianca            "alta", "media" ou "baixa", sobre a sua propria classificacao

REGRAS:
- Nao invente. Campo que nao estiver no texto recebe null. Ano deduzido de referencia
  bibliografica alheia NAO e o ano do documento.
- Livro-texto de estatistica, econometria, probabilidade, otimizacao ou matematica, sem
  aplicacao a transportes, e subarea "metodos_quantitativos".
- Documento que nao e de Engenharia de Transportes nem metodo de apoio a ela recebe
  subarea_principal "fora_de_escopo". Exemplo: manual de linguagem de programacao, gramatica,
  historia geral, psicologia clinica, material pessoal ou financeiro.
- LEI, NORMA, RESOLUCAO OU REGULAMENTO SE CLASSIFICA PELO OBJETO QUE REGULA, e NUNCA como
  "fora_de_escopo" por ser juridico. Estao DENTRO do escopo: Codigo de Transito Brasileiro,
  lei de mobilidade urbana, Estatuto da Cidade, estudo de impacto de vizinhanca, resolucao do
  CONTRAN, da ANTT ou da ANTP, norma da ABNT, e lei de protecao de dados quando aplicada a
  pesquisa de campo. Medido em 18/11/2026: o Codigo de Transito Brasileiro foi mandado para
  "fora_de_escopo" com confianca ALTA por esse engano, em duas edicoes diferentes.
- MAPA, ANEXO, FOLHETO, APRESENTACAO ou material institucional de orgao ou empresa de
  transportes (DER, DNIT, ANTT, concessionaria, iRAP, BID) se classifica pelo OBJETO:
  rede rodoviaria, seguranca viaria, concessao, percepcao do usuario. A forma do documento
  vai no campo natureza; ela nunca decide a subarea e nunca justifica "fora_de_escopo".
- Na duvida entre "fora_de_escopo" e uma subarea de transportes, escolha a SUBAREA e marque
  confianca "baixa". "fora_de_escopo" e sinalizacao para revisao humana, nao e exclusao.
- confianca "baixa" quando o inicio do documento nao bastar para decidir.

CLASSIFIQUE PELO OBJETO DO ESTUDO, NAO PELO TEMA GERAL. Esta e a regra que mais erra.
Estudo que modela a ESCOLHA do individuo (escolha modal, de destino ou de rota por
comportamento; preferencia declarada ou revelada; logit; probit; variavel latente;
valor do tempo; disposicao a pagar) e demanda_escolha, ainda que o texto fale de
trafego, de onibus ou de rodovia. trafego_capacidade e para fluxo, capacidade de via,
intersecao, semaforo e nivel de servico, nao para comportamento do usuario. Metodo
estatistico APLICADO a transportes vai para a subarea do transporte, e nao para
metodos_quantitativos, que e so para livro ou texto de metodo sem aplicacao.

SUBAREAS:
{subareas}

NATUREZAS:
{naturezas}

NOME DO ARQUIVO (pista, nao autoridade): {nome}

INICIO DO DOCUMENTO:
{texto}

FIM DO DOCUMENTO.

CONFIRA ANTES DE RESPONDER. Estas verificacoes vem depois do texto de proposito, e nesta
ordem de proposito. MEDIDO em 18/11/2026, qwen3:14b, Codigo de Transito Brasileiro, 3 execucoes
por variante: regra antes do documento, 3 de 3 erros; a mesma regra depois do documento mas
seguida de outra regra, 3 de 3 erros; a mesma regra como ULTIMA linha do prompt, 3 de 3 acertos.
Vale a ULTIMA instrucao. Quem editar este prompt deve manter a regra de escopo no fim.

A. O estudo modela a ESCOLHA do individuo (escolha modal, de destino ou de rota por
   comportamento; preferencia declarada ou revelada; logit; probit; variavel latente; valor do
   tempo; disposicao a pagar)? Entao e demanda_escolha, ainda que o texto fale de trafego, de
   onibus ou de rodovia. trafego_capacidade e so para fluxo, capacidade de via, intersecao,
   semaforo e nivel de servico, nao para comportamento do usuario.

B. Metodo estatistico APLICADO a transportes vai para a subarea do transporte.
   metodos_quantitativos e so para livro ou texto de metodo sem aplicacao a transportes.

C. Mapa, anexo, folheto ou apresentacao de orgao de transportes se classifica pelo OBJETO.
   A forma vai no campo natureza; ela nunca decide a subarea.

D. fora_de_escopo e sinalizacao para revisao, nunca exclusao, e so cabe quando o documento
   for de outro dominio por inteiro, como manual de linguagem de programacao, gramatica,
   historia geral ou psicologia clinica. Todo fora_de_escopo passa por uma segunda pergunta
   antes de valer, entao nao force a barra para evitar usa-lo.

E. ULTIMA VERIFICACAO, A QUE MAIS ERRA: este documento e lei, norma, resolucao, decreto ou
   regulamento? Entao classifique pelo OBJETO QUE ELE REGULA, e NUNCA como fora_de_escopo por
   ser juridico. Codigo de Transito Brasileiro, lei de mobilidade urbana, Estatuto da Cidade,
   resolucao do CONTRAN ou da ANTT, norma da ABNT, estudo de impacto de vizinhanca e lei de
   protecao de dados aplicada a pesquisa de campo sao todos DENTRO do escopo.
"""


# ----------------------------------------------------------------------------------
# SEGUNDA PASSAGEM: ESCOPO
# O erro de projeto da primeira versao foi juntar DUAS perguntas num enum so. "Que subarea
# e esta?" e "isto pertence ao acervo?" sao perguntas diferentes, e a segunda ficava como
# 13o valor da primeira, competindo com rotulos tematicos.
# Medido em 18/11/2026, qwen3:14b, Codigo de Transito Brasileiro, 3 execucoes por variante:
#   regra de escopo ANTES do documento ................. 0 de 3 corretas
#   regra de escopo depois, seguida de outra regra ...... 0 de 3 corretas
#   regra de escopo como ULTIMA linha do prompt ......... 3 de 3 corretas
# Vale a ULTIMA instrucao. Em vez de depender disso, a decisao de escopo foi separada num
# prompt curto de pergunta unica, onde nao ha outra instrucao para competir.
# Custo: so os documentos que a 1a passagem marcou fora_de_escopo, cerca de 4,5% do acervo.
PROMPT_ESCOPO = """Documento: {titulo}
Arquivo: {nome}

INICIO DO DOCUMENTO:
{texto}

FIM DO DOCUMENTO.

PERGUNTA UNICA: este documento interessa ao trabalho de um engenheiro de planejamento de
transportes? INTERESSA se trata de transporte, transito, mobilidade, logistica, carga,
infraestrutura viaria, ferroviaria, aeroportuaria ou portuaria, uso do solo, ou se e lei,
norma, resolucao ou regulamento sobre esses temas, ou ainda metodo quantitativo com
aplicacao a transportes. NAO INTERESSA so quando for de outro dominio por inteiro.

Se interessar, diga em que subarea ele entra, escolhendo pela DESCRICAO e nao pelo nome
da chave. Lei ou norma sobre transito e transporte entra em planejamento_politica quando
trata de marco legal e politica, ou em trafego_capacidade quando trata de circulacao,
sinalizacao e operacao da via. metodos_quantitativos e so para texto de metodo sem
aplicacao, e nunca para legislacao.

SUBAREAS:
{subareas}"""

ESQUEMA_ESCOPO = {
    "type": "object",
    "properties": {
        "dentro": {"type": "boolean"},
        "subarea": {"type": "string", "enum": sorted(SUB)},
        "motivo": {"type": "string"},
    },
    "required": ["dentro", "subarea", "motivo"],
}


def confirmar_escopo(txt, nome, titulo, modelo):
    """Reexamina um documento que a 1a passagem mandou para fora_de_escopo.

    Devolve (subarea, motivo) ou (None, motivo) se confirmar que esta fora."""
    # AS DESCRICOES VAO NO PROMPT, nao so as chaves. Mesmo erro que custou a 1a passagem:
    # em 18/11 o Codigo de Transito foi recuperado pela 2a passagem mas caiu em
    # metodos_quantitativos, porque o enum oferecia so os nomes das chaves.
    pedido = PROMPT_ESCOPO.format(
        titulo=titulo or "?", nome=nome, texto=txt,
        subareas="\n".join("  %-24s %s" % (k, v) for k, v in SUB.items()
                           if k != "fora_de_escopo"))
    ctx = 8192 if len(pedido) < 18000 else 16384
    bruto, _, _ = llm.chamar_local(modelo, pedido, ctx, 300, 0.1,
                                   esquema=ESQUEMA_ESCOPO, pensar=False)
    try:
        d = json.loads((bruto or "").strip())
    except Exception as e:
        return None, "erro_2a_passagem: %s" % str(e)[:60]
    if not d.get("dentro"):
        return None, (d.get("motivo") or "")[:120]
    sa = d.get("subarea")
    if sa in SUB and sa != "fora_de_escopo":
        return sa, (d.get("motivo") or "")[:120]
    return None, (d.get("motivo") or "")[:120]


def catalogar_um(p, rel, modelo, num_ctx):
    txt, npag = primeiras_paginas(p)
    base = {"arquivo": rel, "paginas": npag, "bytes": p.stat().st_size,
            "hash": hash24(p), "catalogado_em": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if len(txt) < 120:
        base.update({"status": "pendente_ocr", "titulo": None, "autores": [], "ano": None,
                     "veiculo": None, "idioma": None, "natureza": None,
                     "subarea_principal": None, "subarea_secundaria": None,
                     "confianca": None})
        return base
    # AS DESCRICOES VAO NO PROMPT, nao so as chaves. Antes eu mandava apenas os nomes
    # das chaves e o modelo classificava no escuro: de 219 documentos de titulo
    # inequivoco sobre escolha discreta, so 11 (5%) iam para demanda_escolha. Com as
    # descricoes e a regra de desempate, 29 de 30 (97%) numa amostra. Medido em 18/11.
    pedido = PROMPT.format(
        naturezas="\n".join("  %-24s %s" % (k, v) for k, v in NAT.items()),
        subareas="\n".join("  %-24s %s" % (k, v) for k, v in SUB.items()),
        nome=p.name, texto=txt)
    # num_ctx DIMENSIONADO PELO INSUMO. Sem isso o Ollama usa o padrao de 2048 e descarta
    # em silencio a maior parte do prompt, guardando so o final: o catalogo sairia do rodape
    # da terceira pagina em vez da capa. Doutrina do llm.py: nunca truncar em silencio.
    ctx = 8192 if len(pedido) < 18000 else 16384
    bruto, _, _ = llm.chamar_local(modelo, pedido, ctx, 700, 0.1,
                                   esquema=ESQUEMA, pensar=False)
    bruto = (bruto or "").strip()
    try:
        d = json.loads(bruto)
    except Exception as e:
        # com decodificacao restrita isto nao deveria ocorrer; se ocorrer, guardar a resposta
        # INTEIRA, porque diagnostico truncado e diagnostico perdido
        base.update({"status": "erro_json", "resposta_crua": bruto[:4000], "erro": str(e)[:80]})
        return base
    # saneamento: redundante com o enum do esquema, mantido como cinto de seguranca
    if d.get("natureza") not in NAT:
        d["natureza_bruta"], d["natureza"] = d.get("natureza"), None
    if d.get("subarea_principal") not in SUB:
        d["subarea_bruta"], d["subarea_principal"] = d.get("subarea_principal"), None
    if d.get("subarea_secundaria") not in SUB:
        d["subarea_secundaria"] = None
    try:
        a = int(d.get("ano")) if d.get("ano") not in (None, "", "null") else None
        d["ano"] = a if a and 1900 <= a <= 2030 else None
    except Exception:
        d["ano"] = None
    if d.get("subarea_principal") == "fora_de_escopo":
        sa, motivo = confirmar_escopo(txt, p.name, d.get("titulo"), modelo)
        d["escopo_2a_passagem"] = motivo
        if sa:
            d["subarea_principal"] = sa
            d["confianca"] = "baixa"
            d["recuperado_na_2a"] = True
    base.update(d)
    base["status"] = "ok"
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--piloto", type=int, default=0)
    ap.add_argument("--semente", type=int, default=11)
    ap.add_argument("--retomar", action="store_true")
    ap.add_argument("--papel", default="doc")
    a = ap.parse_args()

    raiz = Path(caminho_ubuntu(a.raiz))
    if not raiz.exists():
        sys.exit("ERRO: pasta nao encontrada: %s" % raiz)
    saida = Path(os.path.expanduser(a.saida))
    saida.parent.mkdir(parents=True, exist_ok=True)

    cfg = llm.PAPEIS[a.papel]
    modelo = cfg["modelo"]
    num_ctx = cfg.get("num_ctx") or 0   # nao usado: o ctx e calculado por documento
    print("papel '%s' -> modelo %s (num_ctx por documento, minimo 8192)"
          % (a.papel, modelo), flush=True)

    feitos = {}
    if a.retomar and saida.exists():
        for lin in saida.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(lin)
                # SO o que deu certo conta como feito. Documento marcado pendente_ocr ou com
                # erro precisa voltar na proxima passada, senao o OCR roda e o catalogo
                # nunca aproveita o texto novo.
                if r.get("status") == "ok":
                    feitos[r["arquivo"]] = r.get("hash")
            except Exception:
                pass
        print("ja catalogados: %d" % len(feitos), flush=True)

    pdfs = sorted(p for p in raiz.rglob("*.pdf") if p.is_file())
    print("PDFs no acervo: %d" % len(pdfs), flush=True)
    if a.piloto:
        random.seed(a.semente)
        pdfs = sorted(random.sample(pdfs, min(a.piloto, len(pdfs))))
        print("PILOTO: %d documentos, semente %d" % (len(pdfs), a.semente), flush=True)

    t0, n_ok, n_pend, n_erro, n_pulado = time.time(), 0, 0, 0, 0
    with saida.open("a", encoding="utf-8") as f:
        for i, p in enumerate(pdfs, 1):
            rel = str(p.relative_to(raiz))
            if rel in feitos:
                n_pulado += 1
                continue
            try:
                r = catalogar_um(p, rel, modelo, num_ctx)
            except Exception as e:
                r = {"arquivo": rel, "status": "erro_leitura", "erro": "%s: %s" % (type(e).__name__, str(e)[:90])}
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
            st = r.get("status")
            n_ok += st == "ok"; n_pend += st == "pendente_ocr"
            n_erro += st not in ("ok", "pendente_ocr")
            if i % 10 == 0 or i == len(pdfs):
                dt = time.time() - t0
                print("  %4d/%d  ok %d  ocr %d  erro %d  %.1f s/doc  resta ~%.0f min"
                      % (i, len(pdfs), n_ok, n_pend, n_erro,
                         dt / max(1, i - n_pulado),
                         (len(pdfs) - i) * dt / max(1, i - n_pulado) / 60), flush=True)
    print("FIM: ok %d, pendente_ocr %d, erro %d, pulados %d, %.0f s"
          % (n_ok, n_pend, n_erro, n_pulado, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
