"""Janela do Arrumo-App para o Arrumo-OS (Qt 6, combina com o KDE do Bazzite).

Abas: Diagnóstico (mesmo relatório online do app de Windows), Sensores (hwmon ao
vivo) e Leveza (quanto o sistema gasta parado + atalhos de jogo).
"""
import os
import subprocess
import sys

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                               QProgressBar, QPushButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import VERSAO, coleta, envio, sensores

PASTA = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(PASTA, "logo.png")
COR = {"critico": "#e5484d", "atencao": "#f5a524", "info": "#4cc4dd"}
ROTULO = {"critico": "Crítico", "atencao": "Atenção", "info": "Dica"}

ESTILO = """
QWidget { background: #0f1720; color: #e6edf3; font-size: 10.5pt; }
QTabWidget::pane { border: 1px solid #1f2a36; border-radius: 8px; top: -1px; }
QTabBar::tab { background: #16212c; padding: 8px 18px; margin-right: 2px;
               border-top-left-radius: 8px; border-top-right-radius: 8px; color: #9fb0c0; }
QTabBar::tab:selected { background: #1f2a36; color: #4cc4dd; font-weight: 600; }
QPushButton { background: #4cc4dd; color: #04222a; border: 0; border-radius: 8px;
              padding: 9px 18px; font-weight: 600; }
QPushButton:hover { background: #6fd3e8; }
QPushButton:disabled { background: #2a3a48; color: #6b7d8f; }
QPushButton[secundario="true"] { background: #1f2a36; color: #e6edf3; }
QPushButton[secundario="true"]:hover { background: #2a3a48; }
QFrame[cartao="true"] { background: #16212c; border: 1px solid #1f2a36; border-radius: 10px; }
QTableWidget { background: #16212c; border: 1px solid #1f2a36; border-radius: 8px;
               gridline-color: #1f2a36; }
QHeaderView::section { background: #1f2a36; color: #9fb0c0; border: 0; padding: 6px; }
QProgressBar { background: #1f2a36; border: 0; border-radius: 6px; height: 14px; text-align: center; }
QProgressBar::chunk { background: #4cc4dd; border-radius: 6px; }
QScrollArea { border: 0; }
"""


class Trabalho(QObject):
    """Roda uma função fora da tela para a janela não congelar."""
    pronto = Signal(object)
    erro = Signal(str)

    def __init__(self, func):
        super().__init__()
        self.func = func

    def rodar(self):
        try:
            self.pronto.emit(self.func())
        except Exception as e:
            self.erro.emit(str(e))


def em_segundo_plano(dono, func, ao_terminar, ao_falhar):
    t = QThread(dono)
    w = Trabalho(func)
    w.moveToThread(t)
    t.started.connect(w.rodar)
    w.pronto.connect(ao_terminar)
    w.erro.connect(ao_falhar)
    w.pronto.connect(t.quit)
    w.erro.connect(t.quit)
    t.finished.connect(t.deleteLater)
    dono._trabalhos = getattr(dono, "_trabalhos", []) + [(t, w)]
    t.start()


def gb(valor):
    """16.0 → "16"; 7.4 → "7,4"."""
    return f"{valor or 0:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def cartao(titulo, linhas):
    f = QFrame()
    f.setProperty("cartao", True)
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 12, 14, 12)
    t = QLabel(titulo)
    t.setStyleSheet("color:#4cc4dd; font-weight:600; background:transparent")
    v.addWidget(t)
    for l in linhas:
        lab = QLabel(l)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lab.setStyleSheet("background:transparent")
        v.addWidget(lab)
    return f


# ------------------------------------------------------------------ Diagnóstico

class AbaDiagnostico(QWidget):
    def __init__(self):
        super().__init__()
        self.relatorio = None
        v = QVBoxLayout(self)
        topo = QHBoxLayout()
        self.btn_analisar = QPushButton("Analisar este PC")
        self.btn_analisar.clicked.connect(self.analisar)
        self.btn_enviar = QPushButton("Gerar relatório online")
        self.btn_enviar.setProperty("secundario", True)
        self.btn_enviar.setEnabled(False)
        self.btn_enviar.clicked.connect(self.enviar)
        self.estado = QLabel("Clique em analisar: leva uns segundos e pode pedir autorização para ler os discos.")
        self.estado.setStyleSheet("color:#9fb0c0")
        topo.addWidget(self.btn_analisar)
        topo.addWidget(self.btn_enviar)
        topo.addWidget(self.estado, 1)
        v.addLayout(topo)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.conteudo = QWidget()
        self.lista = QVBoxLayout(self.conteudo)
        self.lista.addStretch()
        self.area.setWidget(self.conteudo)
        v.addWidget(self.area, 1)

    def analisar(self):
        self.btn_analisar.setEnabled(False)
        self.btn_enviar.setEnabled(False)
        self.estado.setText("Analisando o hardware…")
        em_segundo_plano(self, coleta.relatorio, self.mostrar, self.falhou)

    def falhou(self, msg):
        self.btn_analisar.setEnabled(True)
        self.estado.setText("Não deu: " + msg)

    def mostrar(self, r):
        self.relatorio = r
        self.btn_analisar.setEnabled(True)
        self.btn_enviar.setEnabled(True)
        n = len(r["avisos"])
        self.estado.setText("Tudo certo por aqui ✔" if not n else f"{n} ponto(s) para olhar")
        while self.lista.count():
            item = self.lista.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for a in r["avisos"]:
            f = QFrame()
            f.setProperty("cartao", True)
            f.setObjectName("aviso")
            f.setStyleSheet(f"QFrame#aviso{{border-left:4px solid {COR[a['nivel']]}}}")
            h = QVBoxLayout(f)
            t = QLabel(f"<b style='color:{COR[a['nivel']]}'>{ROTULO[a['nivel']]}</b> · <b>{a['titulo']}</b>")
            d = QLabel(a["detalhe"])
            d.setWordWrap(True)
            d.setStyleSheet("color:#c3cfdb; background:transparent")
            t.setStyleSheet("background:transparent")
            h.addWidget(t)
            h.addWidget(d)
            self.lista.addWidget(f)

        m, s, p, pm = r["maquina"], r["sistema"], r["processador"], r["placa_mae"]
        mem = r["memoria"]
        grade = QHBoxLayout()
        col1, col2 = QVBoxLayout(), QVBoxLayout()
        col1.addWidget(cartao("Máquina", [
            " ".join(x for x in (m.get("fabricante"), m.get("modelo")) if x) or m.get("nome_pc", ""),
            f"{m.get('tipo', '')} · {s.get('nome', '')}",
            f"Ligado desde {s.get('ligado_desde', '')}"]))
        col1.addWidget(cartao("Processador", [
            p.get("nome", ""), f"{p.get('nucleos')} núcleos / {p.get('threads')} threads"
            + (f" · até {p['clock_mhz']} MHz" if p.get("clock_mhz") else "")]))
        col1.addWidget(cartao("Placa-mãe", [
            " ".join(x for x in (pm.get("fabricante"), pm.get("modelo")) if x) or "—",
            f"BIOS {pm.get('bios', '')} ({pm.get('bios_data', '')})"]))
        linhas_mem = [f"{gb(mem.get('total_gb'))} GB no total"
                      + (f" · {len(mem['modulos'])} de {mem['slots']} slots" if mem.get("slots") else "")]
        for mod in mem.get("modulos", []):
            vel = mod["velocidade_atual"] or mod["velocidade"]
            partes = [f"{gb(mod['capacidade_gb'])} GB", mod["tipo"], vel and f"{vel} MT/s", mod["fabricante"], mod["modelo"]]
            linhas_mem.append(f"• {mod['slot'] or 'pente'}: " + " ".join(str(x) for x in partes if x))
        col2.addWidget(cartao("Memória", linhas_mem))
        col2.addWidget(cartao("Vídeo", [f"{g['nome']}" + (f" · {gb(g['vram_gb'])} GB" if g.get("vram_gb") else "")
                                        + (f" · driver {g['driver']}" if g.get("driver") else "")
                                        for g in r["placas_video"]] or ["—"]))
        linhas_disco = []
        for d in r["discos"]:
            extra = [x for x in (d.get("saude") and f"saúde {d['saude']}",
                                 d.get("desgaste_pct") is not None and f"{d['desgaste_pct']}% gasto",
                                 d.get("temperatura_c") and f"{d['temperatura_c']} °C",
                                 d.get("horas_ligado") and f"{d['horas_ligado']} h ligado") if x]
            linhas_disco.append(f"• {d['modelo']} ({d['tipo']}, {gb(d['capacidade_gb'])} GB)"
                                + (" — " + ", ".join(extra) if extra else ""))
        col2.addWidget(cartao("Discos", linhas_disco or ["—"]))
        b = r.get("bateria")
        if b:
            col2.addWidget(cartao("Bateria", [f"Saúde {b.get('saude_pct')}%"
                                              + (f" · {b['ciclos']} ciclos" if b.get("ciclos") else "")]))
        col1.addStretch()
        col2.addStretch()
        grade.addLayout(col1, 1)
        grade.addLayout(col2, 1)
        w = QWidget()
        w.setLayout(grade)
        self.lista.addWidget(w)
        self.lista.addStretch()

    def enviar(self):
        self.btn_enviar.setEnabled(False)
        self.estado.setText("Enviando…")
        em_segundo_plano(self, lambda: envio.enviar(self.relatorio), self.enviado, self.falhou_envio)

    def enviado(self, link):
        self.btn_enviar.setEnabled(True)
        self.estado.setText(f"Relatório pronto: {link}")
        QGuiApplication.clipboard().setText(link)
        QDesktopServices.openUrl(QUrl(link))

    def falhou_envio(self, msg):
        self.btn_enviar.setEnabled(True)
        self.estado.setText("Não consegui enviar: " + msg)


# ------------------------------------------------------------------ Sensores

class AbaSensores(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Leitura ao vivo, a cada 2 segundos."))
        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Componente", "Sensor", "Valor"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self.tabela)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar)
        self.timer.start(2000)
        self.atualizar()

    def atualizar(self):
        if not self.isVisible() and self.tabela.rowCount():
            return
        dados = sensores.ler_todos()
        self.tabela.setRowCount(len(dados))
        for i, (comp, rot, val, un) in enumerate(dados):
            txt = f"{val:.0f} {un}" if un in ("RPM", "%") else f"{val:.1f} {un}"
            cel = QTableWidgetItem(txt)
            if un == "°C" and val >= 85:
                cel.setForeground(Qt.red)
            elif un == "°C" and val >= 75:
                cel.setForeground(Qt.yellow)
            for j, t in enumerate((QTableWidgetItem(comp), QTableWidgetItem(rot), cel)):
                self.tabela.setItem(i, j, t)


# ------------------------------------------------------------------ Leveza

DICAS_JOGO = (
    "Opção de inicialização para o CS2 e outros jogos da Steam "
    "(Propriedades do jogo → Geral → Opções de inicialização):"
)
OPCOES = "gamemoderun %command%"
OPCOES_HUD = "MANGOHUD=1 gamemoderun %command%"


class AbaLeveza(QWidget):
    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.addWidget(QLabel("<b>Quanto o sistema está gastando agora</b>"))
        self.cpu = QProgressBar()
        self.ram = QProgressBar()
        self.cpu.setFormat("Processador: %p%")
        self.ram.setFormat("Memória")
        v.addWidget(self.cpu)
        v.addWidget(self.ram)
        self.dica = QLabel()
        self.dica.setWordWrap(True)
        self.dica.setStyleSheet("color:#9fb0c0")
        v.addWidget(self.dica)

        v.addWidget(QLabel("<b>Quem mais segura memória</b>"))
        self.tabela = QTableWidget(0, 2)
        self.tabela.setHorizontalHeaderLabels(["Programa", "Memória"])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        v.addWidget(self.tabela, 1)

        v.addWidget(QLabel("<b>Jogos</b>"))
        lab = QLabel(DICAS_JOGO)
        lab.setWordWrap(True)
        v.addWidget(lab)
        botoes = QHBoxLayout()
        for txt, val in (("Copiar: modo jogo", OPCOES), ("Copiar: modo jogo + FPS na tela", OPCOES_HUD)):
            b = QPushButton(txt)
            b.setProperty("secundario", True)
            b.clicked.connect(lambda _=False, x=val: self.copiar(x))
            botoes.addWidget(b)
        b = QPushButton("Abrir monitor do sistema")
        b.setProperty("secundario", True)
        b.clicked.connect(lambda: subprocess.Popen(["plasma-systemmonitor"]))
        botoes.addWidget(b)
        botoes.addStretch()
        v.addLayout(botoes)
        self.aviso = QLabel()
        self.aviso.setStyleSheet("color:#4cc4dd")
        v.addWidget(self.aviso)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar)
        self.timer.start(3000)

    def copiar(self, txt):
        QGuiApplication.clipboard().setText(txt)
        self.aviso.setText(f"Copiado: {txt}")

    def showEvent(self, e):
        super().showEvent(e)
        self.atualizar()

    def atualizar(self):
        if not self.isVisible():
            return
        u = coleta.uso_agora(0.3)
        self.cpu.setValue(int(u["cpu_pct"]))
        self.ram.setMaximum(int(u["ram_total_gb"] * 100))
        self.ram.setValue(int(u["ram_usada_gb"] * 100))
        self.ram.setFormat(f"Memória: {u['ram_usada_gb']:.1f} de {u['ram_total_gb']:.0f} GB")
        self.dica.setText(
            "Com a área de trabalho parada, o Arrumo-OS costuma ficar entre 1 e 1,5 GB. "
            "Navegador e Discord abertos somam bem mais — feche antes da partida se a memória estiver curta.")
        top = coleta.processos_pesados(10)
        self.tabela.setRowCount(len(top))
        for i, (nome, mb) in enumerate(top):
            self.tabela.setItem(i, 0, QTableWidgetItem(nome))
            self.tabela.setItem(i, 1, QTableWidgetItem(f"{mb} MB" if mb < 1024 else f"{mb / 1024:.1f} GB"))


# ------------------------------------------------------------------ janela

class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Arrumo-App {VERSAO}")
        self.resize(1000, 700)
        if os.path.exists(LOGO):
            self.setWindowIcon(QIcon(LOGO))
        central = QWidget()
        v = QVBoxLayout(central)
        topo = QHBoxLayout()
        if os.path.exists(LOGO):
            logo = QLabel()
            logo.setPixmap(QPixmap(LOGO).scaledToHeight(44, Qt.SmoothTransformation))
            topo.addWidget(logo)
        titulo = QLabel(f"<span style='font-size:15pt;font-weight:600'>Arrumo-App</span>"
                        f"<span style='color:#9fb0c0'> · Arrumo-OS · {VERSAO}</span>")
        topo.addWidget(titulo)
        topo.addStretch()
        v.addLayout(topo)
        abas = QTabWidget()
        abas.addTab(AbaDiagnostico(), "Diagnóstico")
        abas.addTab(AbaSensores(), "Sensores")
        abas.addTab(AbaLeveza(), "Leveza")
        v.addWidget(abas, 1)
        rod = QLabel("Precisa de ajuda? arrumoseupc.com.br")
        rod.setStyleSheet("color:#6b7d8f")
        v.addWidget(rod)
        self.setCentralWidget(central)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Arrumo-App")
    app.setDesktopFileName("br.com.arrumoseupc.App")
    app.setStyleSheet(ESTILO)
    j = Janela()
    j.show()
    return app.exec()
