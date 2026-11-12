"""Fase 1: bracos A (sem OCR) e B (com OCR). Produz texto por pagina."""
import sys, json, pathlib, pymupdf, time
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
B = pathlib.Path.home()/"ecossistema/bench"
PDF = B/"dados/DERPR_Anuario_Estatistico_Seguranca_Rodoviaria_2022_v2.pdf"
T = B/"derpr/textos"; T.mkdir(parents=True, exist_ok=True)
passada = sys.argv[1]
d = pymupdf.open(str(PDF))
for braco, ocr in (("A", False), ("B", True)):
    alvo = T/f"{braco}_p{passada}.json"
    if alvo.exists(): print(f"  braco {braco} passada {passada}: ja existe"); continue
    po = PdfPipelineOptions(); po.do_ocr = ocr; po.do_table_structure = True
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=po)})
    out = {}; t0 = time.time()
    for i in range(58):
        uma = pymupdf.open(); uma.insert_pdf(d, from_page=i, to_page=i)
        tmp = B/f"derpr/_uma.pdf"; uma.save(str(tmp))
        try: out[str(i+1)] = conv.convert(str(tmp)).document.export_to_markdown()
        except Exception as e: out[str(i+1)] = ""
    alvo.write_text(json.dumps(out, ensure_ascii=False))
    v = sum(1 for t in out.values() if len(t.strip()) < 20)
    print(f"  braco {braco} (OCR={ocr}) passada {passada}: {time.time()-t0:.0f}s, {v} paginas quase vazias")
