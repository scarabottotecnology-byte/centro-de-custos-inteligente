"""Gera comercial/Keystone-Apresentacao-Comercial.pdf a partir de slides.html.

Baixa Cormorant Garamond e Manrope (as fontes do site) do Google Fonts, embute
no HTML como base64 e imprime com o Chromium do Playwright via render.cjs.
Uso: python3 comercial/apresentacao/build.py
"""
import base64
import pathlib
import re
import subprocess
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
FONTS = (
    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;"
    "1,400;1,500&family=Manrope:wght@300;400;500;600;700&display=swap"
)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def baixar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req) as r:
        return r.read()


def fontes_embutidas() -> str:
    css = baixar(FONTS).decode()
    faces = []
    # só latin e latin-ext: os outros subconjuntos não são usados e incham o PDF
    for subset, bloco in re.findall(r"/\* ([a-z-]+) \*/\s*(@font-face\s*{[^}]+})", css):
        if subset not in ("latin", "latin-ext"):
            continue
        url = re.search(r"url\((https://[^)]+)\)", bloco).group(1)
        dados = base64.b64encode(baixar(url)).decode()
        faces.append(bloco.replace(url, "data:font/woff2;base64," + dados))
    return "\n".join(faces)


html = (AQUI / "slides.html").read_text()
(AQUI / "build.html").write_text(html.replace("/*FONTS*/", fontes_embutidas(), 1))
subprocess.run(["node", str(AQUI / "render.cjs")], cwd=AQUI, check=True)
