#!/home/mateus/env_transporte/bin/python
# -*- coding: utf-8 -*-
"""converter.py - converte PDF, DOCX, PPTX, XLSX e HTML em Markdown via Docling, com cache por hash.

Receita herdada do lote validado da Linha 20:
  - PDF com texto: Docling sem OCR proprio, TableFormer ACCURATE com cell matching, GPU.
  - PDF digitalizado (--ocr): OCRmyPDF (por, 300 DPI, rotacao limiar 2, deskew) e depois Docling.
Saida com marcadores <!-- pagina N: inicio/fim --> para rastrear a pagina de origem de cada informacao.

  converter.py arquivo.pdf [--ocr] [--forcar] [--saida arquivo.md]
"""
import argparse, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "cache" / "docling"
VERSAO_FORMATO = "v2"  # v2: marcadores de inicio e fim de pagina (v1 gerava citacao deslocada em uma pagina)
FORMATOS = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm"}
MIN_CHARS_PAGINA = 200  # abaixo disso, o PDF provavelmente e imagem sem camada de texto
OCR_CMD = ["ocrmypdf", "-l", "por", "--oversample", "300", "--rotate-pages", "--rotate-pages-threshold", "2",
           "--deskew", "--jobs", "6", "--output-type", "pdf"]


def _hash(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:24]


def _conversor():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (PdfPipelineOptions, TableFormerMode,
                                                    AcceleratorOptions, AcceleratorDevice)
    from docling.document_converter import DocumentConverter, PdfFormatOption
    o = PdfPipelineOptions()
    o.do_ocr = False
    o.do_table_structure = True
    o.table_structure_options.mode = TableFormerMode.ACCURATE
    o.table_structure_options.do_cell_matching = True
    o.accelerator_options = AcceleratorOptions(num_threads=8, device=AcceleratorDevice.CUDA)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=o)})


def _ocr(pdf, destino):
    if not shutil.which("ocrmypdf"):
        raise RuntimeError("ocrmypdf nao instalado; necessario para --ocr")
    r = subprocess.run(OCR_CMD + [str(pdf), str(destino)], capture_output=True, text=True)
    if r.returncode == 6:  # pagina ja tinha texto: refaz forcando OCR em todas
        r = subprocess.run(OCR_CMD + ["--force-ocr", str(pdf), str(destino)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"OCRmyPDF falhou (codigo {r.returncode}): {r.stderr.strip()[-300:]}")
    return destino


def converter(caminho, ocr=False, forcar=False):
    """Retorna (caminho_md, info). Usa cache quando o mesmo arquivo ja foi convertido com a mesma opcao."""
    p = Path(caminho)
    suf = p.suffix.lower()
    if suf not in FORMATOS:
        raise ValueError(f"formato {suf} nao suportado pelo conversor")
    CACHE.mkdir(parents=True, exist_ok=True)
    chave = f"{VERSAO_FORMATO}_{_hash(p)}" + ("_ocr" if ocr else "")
    md, meta = CACHE / f"{chave}.md", CACHE / f"{chave}.json"
    if md.exists() and meta.exists() and not forcar:
        info = json.loads(meta.read_text(encoding="utf-8")); info["cache"] = True
        return md, info
    t = time.time()
    origem = _ocr(p, CACHE / f"{chave}_ocr.pdf") if (ocr and suf == ".pdf") else p
    doc = _conversor().convert(str(origem)).document
    n = len(getattr(doc, "pages", {}) or {})
    if suf == ".pdf" and n:
        texto = "\n\n".join(f"<!-- pagina {i}: inicio -->\n\n{doc.export_to_markdown(page_no=i)}\n\n<!-- pagina {i}: fim -->"
                              for i in range(1, n + 1))
    else:
        texto = doc.export_to_markdown()
    from importlib.metadata import version
    metodo = ("OCRmyPDF por 300dpi + " if ocr else "") + f"Docling {version('docling')} sem OCR proprio, tabelas accurate"
    md.write_text(f"<!-- origem: {p.name} | sha256 {chave} | {metodo} -->\n\n{texto}", encoding="utf-8")
    uteis = len(texto) - 20 * n
    info = {"arquivo": p.name, "paginas": n, "tabelas": len(doc.tables), "caracteres": len(texto),
            "seg": round(time.time() - t, 1), "ocr": ocr, "cache": False,
            "suspeita_digitalizado": bool(suf == ".pdf" and not ocr and n and uteis / n < MIN_CHARS_PAGINA)}
    meta.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return md, info


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Conversor Docling do ecossistema")
    ap.add_argument("arquivo"); ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--forcar", action="store_true"); ap.add_argument("--saida")
    a = ap.parse_args()
    md, info = converter(a.arquivo, a.ocr, a.forcar)
    if a.saida:
        shutil.copy2(md, a.saida); info["saida"] = a.saida
    info["markdown"] = str(md)
    print(json.dumps(info, ensure_ascii=False))
