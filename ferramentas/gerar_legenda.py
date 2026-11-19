#!/usr/bin/env python3
"""Gera legenda .ass (amarela, embaixo) casando a letra linha a linha com os tempos
de palavra de uma transcrição (formato ElevenLabs: {"words":[{"text","start","end","type"}]}).

Uso: python3 gerar_legenda.py letra.txt palavras.json saida.ass
"""
import json
import re
import sys
import unicodedata


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", w)


def ts(t):
    t = max(0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def main(letra, palavras, saida):
    linhas = [l.strip() for l in open(letra, encoding="utf-8") if l.strip() and not l.startswith("[")]
    words = [w for w in json.load(open(palavras))["words"] if w.get("type", "word") == "word"]
    wn = [norm(w["text"]) for w in words]
    pos, eventos = 0, []
    for linha in linhas:
        toks = [norm(t) for t in linha.split() if norm(t)]
        # procura a primeira palavra da linha a partir da posição atual
        ini = next((i for i in range(pos, min(pos + 12, len(wn))) if wn[i] == toks[0]), pos)
        fim = min(ini + len(toks) - 1, len(words) - 1)
        eventos.append([words[ini]["start"], words[fim]["end"], linha])
        pos = fim + 1
    for e in eventos:
        e[0] -= 0.15
    for i, e in enumerate(eventos):
        prox = eventos[i + 1][0] if i + 1 < len(eventos) else e[1] + 3
        e[1] = min(e[1] + 0.8, prox - 0.05)

    cab = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Letra,DejaVu Sans,62,&H0000FFFF,&H0000FFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,4,2,2,80,80,170,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(saida, "w", encoding="utf-8") as f:
        f.write(cab)
        for a, b, txt in eventos:
            f.write(f"Dialogue: 0,{ts(a)},{ts(b)},Letra,,0,0,0,,{{\\fad(150,150)}}{txt}\n")
    for a, b, txt in eventos:
        print(f"{a:7.2f}-{b:7.2f} {txt}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
