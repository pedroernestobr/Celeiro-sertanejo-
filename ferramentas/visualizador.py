#!/usr/bin/env python3
"""Gera um vídeo em tons de cinza com barras de equalizador que seguem a música.
Branco = barra, preto = transparente (usado como máscara de alfa na montagem).

Uso: python3 visualizador.py musica.mp3 saida.mp4 [fps]
"""
import subprocess
import sys

import numpy as np

W, H = 504, 110
N_BARRAS, LARG, GAP = 28, 14, 4
SR = 22050


def main(musica, saida, fps=25):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", musica, "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    hop = SR // fps
    n_frames = len(a) // hop
    win = 2048
    jan = np.hanning(win)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    bordas = np.geomspace(50, 8000, N_BARRAS + 1)
    idx = [(np.searchsorted(freqs, bordas[i]), max(np.searchsorted(freqs, bordas[i + 1]),
            np.searchsorted(freqs, bordas[i]) + 1)) for i in range(N_BARRAS)]
    a = np.pad(a, (win // 2, win))
    energia = np.zeros((n_frames, N_BARRAS), dtype=np.float32)
    for f in range(n_frames):
        seg = a[f * hop: f * hop + win] * jan
        mag = np.abs(np.fft.rfft(seg))
        energia[f] = [mag[i:j].mean() for i, j in idx]
    db = 20 * np.log10(energia + 1e-6)
    # normaliza cada barra pelo próprio percentil para todas se mexerem
    lo = np.percentile(db, 20, axis=0)
    hi = np.percentile(db, 99, axis=0)
    nivel = np.clip((db - lo) / (hi - lo + 1e-6), 0, 1) ** 1.4

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
                             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264",
                             "-crf", "12", "-pix_fmt", "yuv420p", saida], stdin=subprocess.PIPE)
    atual = np.zeros(N_BARRAS)
    for f in range(n_frames):
        atual = np.maximum(nivel[f], atual * 0.82)
        img = np.zeros((H, W), dtype=np.uint8)
        for b in range(N_BARRAS):
            h = max(4, int(atual[b] * H))
            x = b * (LARG + GAP)
            img[H - h:, x:x + LARG] = 255
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 25)
