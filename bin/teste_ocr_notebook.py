# -*- coding: utf-8 -*-
"""Teste FUNCIONAL da cadeia de OCR. Nao confere se o programa existe:
confere se ele devolve o texto certo a partir de uma imagem."""
import os, shutil, subprocess, tempfile

d = tempfile.mkdtemp(prefix="teste_ocr_")
os.chdir(d)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

F1 = "RELATORIO TECNICO DE TRANSPORTES"
F2 = "Secao 3: divisao modal e pesquisa de preferencia declarada"
fig = plt.figure(figsize=(8.27, 11.69))
fig.text(0.08, 0.82, F1, fontsize=22)
fig.text(0.08, 0.77, F2, fontsize=13)
fig.savefig("origem.pdf")
plt.close(fig)
print("1. PDF gerado ............ %d bytes" % os.path.getsize("origem.pdf"))

r = subprocess.run(["pdftoppm", "-r", "300", "-png", "origem.pdf", "pag"],
                   capture_output=True, text=True)
imgs = sorted(f for f in os.listdir(".") if f.endswith(".png"))
if not imgs:
    print("2. rasterizacao FALHOU:", r.stderr.strip()[:120])
    raise SystemExit(1)
print("2. rasterizado ........... %s, %d bytes (agora e imagem, sem texto)"
      % (imgs[0], os.path.getsize(imgs[0])))

r = subprocess.run(["tesseract", imgs[0], "stdout", "-l", "por"],
                   capture_output=True, text=True)
import unicodedata
def sem_acento(t):
    """O tesseract com -l por RESTAURA acentos que a imagem nao tinha.
    Comparar sem acento evita reprovar um OCR que acertou."""
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").upper()
txt = sem_acento(r.stdout or "")
ok1 = "RELATORIO" in txt
ok2 = "DECLARADA" in txt
print("3. OCR devolveu .......... %d caracteres" % len(r.stdout.strip()))
print("   achou 'RELATORIO' ..... %s" % ok1)
print("   achou 'DECLARADA' ..... %s" % ok2)
print("   trecho lido ........... %s" % " ".join(r.stdout.split())[:80])

try:
    # O executavel do ocrmypdf mora ao lado do python do venv. Chamar so
    # "ocrmypdf" depende do PATH, que nao inclui ~/venv_lote/bin quando se
    # invoca o interpretador por caminho absoluto: por isso o caminho completo.
    import sys
    exe = os.path.join(os.path.dirname(sys.executable), "ocrmypdf")
    if not os.path.exists(exe):
        exe = "ocrmypdf"
    r = subprocess.run([exe, "-l", "por", "--force-ocr", "--quiet",
                        "origem.pdf", "saida.pdf"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode == 0:
        t = subprocess.run(["pdftotext", "saida.pdf", "-"],
                           capture_output=True, text=True).stdout
        print("4. ocrmypdf OK ........... camada de texto com %d caracteres"
              % len(t.strip()))
    else:
        print("4. ocrmypdf FALHOU ....... %s" % r.stderr.strip()[:140])
except FileNotFoundError:
    print("4. ocrmypdf .............. AUSENTE no venv_lote")
except Exception as e:
    print("4. ocrmypdf .............. erro: %s" % e)

# 5. --clean exige o unpaper, que endireita e limpa pagina escaneada torta.
#    Sem ele o ocrmypdf recusa a opcao; o resto continua funcionando.
limpo = False
try:
    import sys as _s
    _exe = os.path.join(os.path.dirname(_s.executable), "ocrmypdf")
    if not os.path.exists(_exe):
        _exe = "ocrmypdf"
    r = subprocess.run([_exe, "-l", "por", "--force-ocr", "--clean", "--quiet",
                        "origem.pdf", "limpa.pdf"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode == 0 and os.path.exists("limpa.pdf"):
        limpo = True
        print("5. ocrmypdf --clean OK .... %d bytes (unpaper no ar)"
              % os.path.getsize("limpa.pdf"))
    else:
        print("5. ocrmypdf --clean FALHOU %s" % r.stderr.strip()[:140])
except Exception as e:
    print("5. ocrmypdf --clean ....... erro: %s" % e)

print("VEREDITO: %s" % ("OCR FUNCIONA" if (ok1 and ok2) else "OCR NAO FUNCIONA"))
print("LIMPEZA DE PAGINA: %s" % ("DISPONIVEL" if limpo else "INDISPONIVEL"))
shutil.rmtree(d, ignore_errors=True)
