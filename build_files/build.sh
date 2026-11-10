#!/bin/bash
# Tudo que o Arrumo-OS muda em cima do Bazzite. Roda dentro do build da imagem.
set -ouex pipefail

cp -avf /ctx/system_files/. /

# Arrumo-App (Qt 6) e o que o diagnóstico lê: SMART, pentes de memória, PCI
dnf5 install -y --setopt=install_weak_deps=False \
    python3-pyside6 smartmontools dmidecode pciutils lm_sensors

python3 -m compileall -q /usr/lib/arrumo-app

# Nome do sistema na tela de login / "Sobre". ID e VARIANT_ID ficam os do Bazzite:
# os scripts dele (ujust, atualizador) se guiam por eles.
VERSAO_BASE=$(. /usr/lib/os-release && echo "${VERSION_ID:-}")
sed -i "s|^PRETTY_NAME=.*|PRETTY_NAME=\"Arrumo-OS (base Bazzite ${VERSAO_BASE})\"|" /usr/lib/os-release

gtk-update-icon-cache -f /usr/share/icons/hicolor || true

# Qual das duas imagens é esta: o arrumo-gpu.service compara com a placa da máquina
echo "${ARRUMO_VARIANTE:-amd}" > /usr/share/arrumo-os/variante
systemctl enable arrumo-gpu.service

# Chrome e outros Flatpaks: instalados no primeiro boot (lista em /usr/share/arrumo-os/flatpaks)
systemctl enable arrumo-flatpaks.service

# Resto do dnf fora do cache montado (o `bootc container lint` reclama de /var e /run com conteúdo)
rm -rf /var/lib/dnf /run/dnf
