"""Lê o hardware e monta o relatório no MESMO formato do Arrumo-App de Windows.

O JSON vai para o mesmo `POST /api/diagnostico` e é lido pelo mesmo template
(`diagnostico_publico.html`) — nome de campo diferente do `Relatorio.cs` é campo
que some no relatório online. O que só o root enxerga (SMART, pentes, série)
vem do `coleta-root` via pkexec; sem ele o relatório sai com `admin: false`.
"""
import json
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime

from . import VERSAO

COLETA_ROOT = "/usr/libexec/arrumo-app/coleta-root"
GENERICO = re.compile(r"to be filled|default string|system product|not specified|^none$|^0+$", re.I)


def ler(caminho, padrao=""):
    try:
        with open(caminho) as f:
            return f.read().strip()
    except OSError:
        return padrao


def limpo(texto):
    texto = (texto or "").strip()
    return "" if GENERICO.search(texto) else texto


def rodar(*cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def coleta_root():
    """Devolve (dados, ok). Recusado ou sem pkexec, segue sem."""
    if os.geteuid() == 0:
        saida = rodar("/usr/bin/python3", "-I", COLETA_ROOT, timeout=120)
    else:
        saida = rodar("pkexec", COLETA_ROOT, timeout=120)
    try:
        return json.loads(saida), True
    except ValueError:
        return {}, False


# ---------------------------------------------------------------- partes

def maquina(raiz):
    dmi = "/sys/class/dmi/id/"
    chassi = int(ler(dmi + "chassis_type", "0") or 0)
    notebook = chassi in (8, 9, 10, 11, 14, 30, 31, 32) or any(
        n.startswith("BAT") for n in _lista("/sys/class/power_supply"))
    return {
        "nome_pc": socket.gethostname(),
        "fabricante": limpo(ler(dmi + "sys_vendor")),
        "modelo": limpo(ler(dmi + "product_name")),
        "tipo": "Notebook" if notebook else "Desktop",
        "serie": limpo(raiz.get("serie", "")),
    }


def sistema():
    osr = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', ler("/etc/os-release"), re.M))
    boot = None
    for linha in ler("/proc/stat").splitlines():
        if linha.startswith("btime"):
            boot = datetime.fromtimestamp(int(linha.split()[1]))
    return {
        "nome": osr.get("PRETTY_NAME", "Linux"),
        "versao": osr.get("VERSION_ID", ""),
        "build": platform.release(),
        "arquitetura": "64 bits" if platform.machine() in ("x86_64", "aarch64") else platform.machine(),
        "instalado_em": "",
        "ligado_desde": boot.strftime("%d/%m/%Y %H:%M") if boot else "",
    }


def processador():
    info = ler("/proc/cpuinfo")
    nome = (re.search(r"^model name\s*:\s*(.+)$", info, re.M) or [None, ""])[1]
    nucleos = len(set(re.findall(r"^physical id\s*:\s*(\d+).*?^core id\s*:\s*(\d+)", info, re.M | re.S))) or None
    threads = os.cpu_count() or 0
    mhz = int(ler("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq", "0") or 0) // 1000
    lscpu = rodar("lscpu")
    m = re.search(r"^Core\(s\) per socket:\s*(\d+)", lscpu, re.M)
    s = re.search(r"^Socket\(s\):\s*(\d+)", lscpu, re.M)
    if m:
        nucleos = int(m.group(1)) * (int(s.group(1)) if s else 1)
    return {
        "nome": re.sub(r"\s+", " ", nome).strip(),
        "nucleos": nucleos or threads,
        "threads": threads,
        "clock_mhz": mhz,
        "soquete": "",
    }


def placa_mae():
    dmi = "/sys/class/dmi/id/"
    data = ler(dmi + "bios_date")          # mm/dd/aaaa
    m = re.match(r"(\d\d)/(\d\d)/(\d{4})", data)
    return {
        "fabricante": limpo(ler(dmi + "board_vendor")),
        "modelo": limpo(ler(dmi + "board_name")),
        "bios": ler(dmi + "bios_version"),
        "bios_data": f"{m.group(2)}/{m.group(1)}/{m.group(3)}" if m else "",
    }


def memoria(raiz):
    total_kb = int((re.search(r"MemTotal:\s*(\d+)", ler("/proc/meminfo")) or [0, 0])[1])
    mem = raiz.get("memoria") or {}
    modulos = mem.get("modulos") or []
    total = sum(m["capacidade_gb"] for m in modulos) or round(total_kb / 1024 / 1024, 1)
    return {"total_gb": total, "slots": mem.get("slots", 0), "modulos": modulos}


def placas_video():
    placas = []
    for card in sorted(_lista("/sys/class/drm")):
        if not re.fullmatch(r"card\d+", card):
            continue
        dev = f"/sys/class/drm/{card}/device/"
        slot = os.path.basename(os.path.realpath(dev))
        nome = re.sub(r"^[^:]+:\s*", "", rodar("lspci", "-s", slot).strip().split("\n")[0])
        nome = re.sub(r"^[^:]*controller:\s*", "", nome, flags=re.I)
        nome = re.sub(r"\s*\(rev [0-9a-f]+\)$", "", nome)
        driver = os.path.basename(os.path.realpath(dev + "driver")) if os.path.exists(dev + "driver") else ""
        vram = ler(dev + "mem_info_vram_total")            # amdgpu
        vram_gb = round(int(vram) / 1024 ** 3, 1) if vram.isdigit() else None
        if driver == "nvidia":
            q = rodar("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits")
            partes = [p.strip() for p in q.split("\n")[0].split(",")]
            if len(partes) == 3:
                nome, vram_gb, driver = partes[0], round(int(partes[1]) / 1024, 1), "nvidia " + partes[2]
        placas.append({"nome": nome or card, "vram_gb": vram_gb, "driver": driver, "driver_data": ""})
    return placas


def discos(raiz):
    smart = raiz.get("discos") or {}
    raiz_dev = _disco_da_raiz()
    lista = []
    for nome in sorted(_lista("/sys/block")):
        if re.match(r"(loop|ram|zram|dm-|sr|md|nbd)", nome):
            continue
        base = f"/sys/block/{nome}/"
        setores = int(ler(base + "size", "0") or 0)
        if setores == 0:
            continue
        usb = "/usb" in os.path.realpath(base)
        rotativo = ler(base + "queue/rotational") == "1"
        s = smart.get(nome) or {}
        if usb:
            tipo = "USB"
        elif nome.startswith("nvme"):
            tipo = "SSD NVMe"
        elif rotativo and s.get("rotacao") != 0:
            tipo = "HD"
        else:
            tipo = "SSD SATA"
        lista.append({
            "modelo": ler(base + "device/model") or nome,
            "tipo": tipo,
            "capacidade_gb": round(setores * 512 / 1000 ** 3, 1),
            "saude": s.get("saude", ""),
            "desgaste_pct": s.get("desgaste_pct"),
            "temperatura_c": s.get("temperatura_c"),
            "horas_ligado": s.get("horas_ligado"),
            "sistema": nome == raiz_dev,
        })
    return lista


def volumes():
    """Pontos de montagem de verdade (o /sysroot e os bind mounts do ostree ficam de fora)."""
    vistos, saida = set(), []
    for linha in ler("/proc/mounts").splitlines():
        dev, ponto, fs = linha.split()[:3]
        if not dev.startswith("/dev/") or fs in ("squashfs", "iso9660", "overlay") or dev in vistos:
            continue
        if ponto.startswith(("/sysroot", "/boot", "/usr", "/etc", "/run", "/snap")):
            continue
        vistos.add(dev)
        try:
            st = os.statvfs(ponto)
        except OSError:
            continue
        total = st.f_blocks * st.f_frsize / 1000 ** 3
        if total < 1:
            continue
        saida.append({"letra": ponto, "rotulo": os.path.basename(dev),
                      "total_gb": round(total, 1), "livre_gb": round(st.f_bavail * st.f_frsize / 1000 ** 3, 1)})
    return saida


def bateria():
    for n in sorted(_lista("/sys/class/power_supply")):
        if not n.startswith("BAT"):
            continue
        b = f"/sys/class/power_supply/{n}/"
        # energy_* em µWh; alguns notebooks só têm charge_* (µAh) — vira mWh pela tensão nominal
        projeto, atual = ler(b + "energy_full_design"), ler(b + "energy_full")
        fator = 1000
        if not projeto.isdigit():
            projeto, atual = ler(b + "charge_full_design"), ler(b + "charge_full")
            volts = int(ler(b + "voltage_min_design", "0") or 0) / 1e6
            fator = 1000 / volts if volts else None
        if not (projeto.isdigit() and atual.isdigit() and fator):
            continue
        p, a = int(projeto) / fator, int(atual) / fator
        ciclos = ler(b + "cycle_count")
        return {
            "saude_pct": min(100, round(a * 100 / p)) if p else None,
            "capacidade_projeto_mwh": round(p),
            "capacidade_atual_mwh": round(a),
            "ciclos": int(ciclos) if ciclos.isdigit() and int(ciclos) > 0 else None,
        }
    return None


def rede():
    saida = []
    for n in sorted(_lista("/sys/class/net")):
        b = f"/sys/class/net/{n}/"
        if n == "lo" or not os.path.exists(b + "device"):       # só placa física
            continue
        wifi = os.path.exists(b + "wireless")
        vel = ler(b + "speed")
        saida.append({
            "nome": n,
            "tipo": "Wi-Fi" if wifi else "Cabo",
            "velocidade_mbps": int(vel) if vel.lstrip("-").isdigit() and int(vel) > 0 else None,
        })
    return saida


def _lista(pasta):
    try:
        return os.listdir(pasta)
    except OSError:
        return []


def _disco_da_raiz():
    for linha in ler("/proc/mounts").splitlines():
        dev, ponto = linha.split()[:2]
        if ponto in ("/sysroot", "/") and dev.startswith("/dev/"):
            nome = os.path.basename(os.path.realpath(dev))
            # partição → disco (nvme0n1p3 → nvme0n1, sda2 → sda; dm-0 do LUKS → disco por trás dele)
            escravos = _lista(f"/sys/class/block/{nome}/slaves")
            if escravos:
                nome = escravos[0]
            pai = os.path.basename(os.path.dirname(os.path.realpath(f"/sys/class/block/{nome}")))
            return pai if os.path.exists(f"/sys/block/{pai}") else nome
    return ""


# ---------------------------------------------------------------- tudo junto

def relatorio(testes=None):
    from .avisos import gerar
    raiz, admin = coleta_root()
    partes = {
        "maquina": lambda: maquina(raiz), "sistema": sistema, "processador": processador,
        "placa_mae": placa_mae, "memoria": lambda: memoria(raiz), "placas_video": placas_video,
        "discos": lambda: discos(raiz), "volumes": volumes, "bateria": bateria, "rede": rede,
    }
    r = {"versao_app": f"Linux {VERSAO}", "gerado_em": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
         "admin": admin}
    for chave, f in partes.items():
        try:
            r[chave] = f()
        except Exception:          # parte que falha não derruba o relatório
            r[chave] = [] if chave in ("placas_video", "discos", "volumes", "rede") else (None if chave == "bateria" else {})
    r["testes"] = testes
    r["avisos"] = gerar(r)
    return r


def uso_agora(intervalo=0.5):
    """CPU (%) e RAM para a aba Leveza."""
    def tempos():
        v = [int(x) for x in ler("/proc/stat").splitlines()[0].split()[1:]]
        return sum(v), v[3] + v[4]
    t1, o1 = tempos()
    time.sleep(intervalo)
    t2, o2 = tempos()
    cpu = 100 * (1 - (o2 - o1) / max(1, t2 - t1))
    mi = dict((k, int(v.split()[0])) for k, v in re.findall(r"^(\w+):\s*(.+)$", ler("/proc/meminfo"), re.M))
    total = mi["MemTotal"] / 1024 / 1024
    usada = (mi["MemTotal"] - mi["MemAvailable"]) / 1024 / 1024
    return {"cpu_pct": round(cpu, 1), "ram_total_gb": round(total, 1), "ram_usada_gb": round(usada, 2)}


def processos_pesados(n=10):
    """Os que mais seguram memória, somando os processos de mesmo nome (o Chrome vira um só)."""
    soma = {}
    for pid in _lista("/proc"):
        if not pid.isdigit():
            continue
        st = ler(f"/proc/{pid}/status")
        nome = (re.search(r"^Name:\s*(.+)$", st, re.M) or [None, ""])[1]
        rss = re.search(r"^VmRSS:\s*(\d+)", st, re.M)
        if nome and rss:
            soma[nome] = soma.get(nome, 0) + int(rss.group(1))
    top = sorted(soma.items(), key=lambda x: -x[1])[:n]
    return [(nome, round(kb / 1024)) for nome, kb in top]
