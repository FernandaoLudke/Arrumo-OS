"""Temperaturas, ventoinhas e consumo lidos direto do /sys/class/hwmon (o kernel já
expõe tudo; não precisa de driver extra como o PawnIO do Windows)."""
import glob
import os
import re

NOMES = {
    "k10temp": "Processador (AMD)", "coretemp": "Processador (Intel)", "zenpower": "Processador (AMD)",
    "amdgpu": "Placa de vídeo (AMD)", "nouveau": "Placa de vídeo (NVIDIA)", "i915": "Vídeo Intel",
    "xe": "Vídeo Intel", "nvme": "SSD NVMe", "drivetemp": "Disco", "acpitz": "Placa-mãe (ACPI)",
    "iwlwifi_1": "Wi-Fi", "BAT0": "Bateria",
}


def _ler(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return ""


def ler_todos():
    """Lista de (componente, leitura, valor, unidade)."""
    saida = []
    for h in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        nome = _ler(h + "/name")
        comp = NOMES.get(nome, nome)
        for arq in sorted(glob.glob(h + "/temp*_input")):
            v = _ler(arq)
            if not v.lstrip("-").isdigit():
                continue
            rot = _ler(arq.replace("_input", "_label")) or os.path.basename(arq).split("_")[0]
            saida.append((comp, rot, int(v) / 1000, "°C"))
        for arq in sorted(glob.glob(h + "/fan*_input")):
            v = _ler(arq)
            if v.isdigit():
                rot = _ler(arq.replace("_input", "_label")) or "ventoinha " + re.sub(r"\D", "", os.path.basename(arq))
                saida.append((comp, rot, int(v), "RPM"))
        for arq in sorted(glob.glob(h + "/power*_average")) + sorted(glob.glob(h + "/power*_input")):
            v = _ler(arq)
            if v.isdigit():
                saida.append((comp, "consumo", int(v) / 1e6, "W"))
    # NVIDIA proprietário não aparece no hwmon
    if os.path.exists("/proc/driver/nvidia"):
        import subprocess
        try:
            q = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,fan.speed",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
            t, p, f = [x.strip() for x in q.split("\n")[0].split(",")]
            saida.append(("Placa de vídeo (NVIDIA)", "GPU", float(t), "°C"))
            if p.replace(".", "").isdigit():
                saida.append(("Placa de vídeo (NVIDIA)", "consumo", float(p), "W"))
            if f.isdigit():
                saida.append(("Placa de vídeo (NVIDIA)", "ventoinha", int(f), "%"))
        except Exception:
            pass
    return saida
