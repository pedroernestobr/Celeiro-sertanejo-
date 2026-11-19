#!/usr/bin/env python3
"""Monta um clipe do Celeiro Sertanejo a partir de imagens + música, sem gastar crédito.

Uso: python3 montar_clipe.py roteiro.json saida.mp4

roteiro.json:
{
  "musica": "caminho/musica.mp3",
  "pasta_imagens": "caminho/imagens",
  "fps": 25,
  "transicao": 0.6,
  "cenas": [ {"img": "c01.jpeg", "dur": 8, "efeito": "zin"}, ... ],
  "textos": [ {"texto": "CELEIRO SERTANEJO", "inicio": 0.5, "dur": 4, "pos": "baixo"} ]
}

Efeitos: zin (zoom entrando), zout (zoom saindo), pl (desliza para a direita),
pr (desliza para a esquerda). Cada cena dura "dur" segundos na linha do tempo.
"""
import json
import os
import subprocess
import sys
import tempfile

W, H = 1920, 1080
FONTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def zoompan(efeito, n):
    p = f"on/{n}"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if efeito == "zin":
        return f"z='1+0.15*{p}':x='{cx}':y='{cy}'"
    if efeito == "zout":
        return f"z='1.15-0.15*{p}':x='{cx}':y='{cy}'"
    if efeito == "pl":
        return f"z='1.15':x='(iw-iw/zoom)*{p}':y='{cy}'"
    if efeito == "pr":
        return f"z='1.15':x='(iw-iw/zoom)*(1-{p})':y='{cy}'"
    raise ValueError(efeito)


def run(cmd):
    subprocess.run(cmd, check=True)


def main(roteiro_path, saida):
    r = json.load(open(roteiro_path))
    base = os.path.dirname(os.path.abspath(roteiro_path))
    pasta = os.path.join(base, r["pasta_imagens"])
    musica = os.path.join(base, r["musica"])
    fps, tr = r.get("fps", 25), r.get("transicao", 0.6)
    cenas = r["cenas"]
    tmp = tempfile.mkdtemp(prefix="clipe_")

    segs = []
    for i, c in enumerate(cenas):
        ultima = i == len(cenas) - 1
        dur = c["dur"] + (0 if ultima else tr)
        n = int(round(dur * fps))
        out = os.path.join(tmp, f"s{i:02d}.mp4")
        vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
              f"zoompan={zoompan(c['efeito'], n)}:d={n}:s={W}x{H}:fps={fps},format=yuv420p")
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(pasta, c["img"]), "-vf", vf,
             "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out])
        segs.append(out)
        print(f"cena {i+1}/{len(cenas)} ok", flush=True)

    # cadeia de xfade
    inputs, filt, prev, t = [], [], "[0:v]", 0.0
    for s in segs:
        inputs += ["-i", s]
    for i in range(1, len(segs)):
        t += cenas[i - 1]["dur"]
        lbl = f"[v{i}]"
        filt.append(f"{prev}[{i}:v]xfade=transition=fade:duration={tr}:offset={t:.3f}{lbl}")
        prev = lbl
    total = sum(c["dur"] for c in cenas)

    # textos
    for j, tx in enumerate(r.get("textos", [])):
        y = "h*0.80" if tx.get("pos", "baixo") == "baixo" else "h*0.10"
        a, d = tx["inicio"], tx["dur"]
        alpha = f"if(lt(t,{a}+0.5),(t-{a})/0.5,if(gt(t,{a+d}-0.5),({a+d}-t)/0.5,1))"
        lbl = f"[t{j}]"
        texto = tx["texto"].replace(":", r"\:").replace("'", "")
        filt.append(f"{prev}drawtext=fontfile={FONTE}:text='{texto}':fontsize={tx.get('tamanho', 64)}:"
                    f"fontcolor=white:borderw=4:bordercolor=black@0.8:x=(w-text_w)/2:y={y}:"
                    f"enable='between(t,{a},{a+d})':alpha='{alpha}'{lbl}")
        prev = lbl
    # marca d'água do canal (canto inferior esquerdo)
    marca = r.get("marca")
    if marca:
        filt.append(f"{prev}drawtext=fontfile={FONTE}:text='{marca}':fontsize=44:fontcolor=white@0.9:"
                    f"shadowcolor=black@0.6:shadowx=2:shadowy=2:x=48:y=h-th-44[mk]")
        prev = "[mk]"
    # animação de som (barras de frequência, canto inferior direito)
    na = len(segs)
    amap = f"{na}:a"
    extra = []
    if r.get("visualizador"):
        viz = os.path.join(tmp, "viz.mp4")
        run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualizador.py"),
             musica, viz, str(fps)])
        extra = ["-i", viz]
        filt.append(f"[{na+1}:v]format=gray,scale=504:110[m]")
        filt.append(f"color=c=white:s=504x110:r={fps}[w]")
        filt.append("[w][m]alphamerge,colorchannelmixer=aa=0.8[viz]")
        filt.append(f"{prev}[viz]overlay=x=W-w-48:y=H-h-40:shortest=1[vz]")
        prev = "[vz]"
    filt.append(f"{prev}fade=t=in:st=0:d=1,fade=t=out:st={total-2}:d=2[vout]")
    fscript = os.path.join(tmp, "filtro.txt")
    open(fscript, "w").write(";\n".join(filt))

    run(["ffmpeg", "-v", "error", "-y", *inputs, "-i", musica, *extra, "-filter_complex_script", fscript,
         "-map", "[vout]", "-map", amap, "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida])
    print("pronto:", saida, f"{total:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
