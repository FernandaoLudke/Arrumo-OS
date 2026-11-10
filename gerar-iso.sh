#!/usr/bin/env bash
# Gera a ISO do Arrumo-OS aqui na VPS e publica no sistema (download só admin, em
# /diagnosticos → botão Arrumo-OS). Mesmo papel do arrumo-app/publicar.sh.
#
#   ./gerar-iso.sh            build da imagem + ISO + publica
#   ./gerar-iso.sh --so-imagem  só o build (para testar o Containerfile)
#   ./gerar-iso.sh --so-iso     pula o build: usa a imagem que já está no podman
#
# O build é no Docker (BuildKit); a ISO sai do bootc-image-builder, que lê a imagem do
# storage do podman — por isso a cópia com skopeo no meio. O bootc-image-builder oficial
# é CentOS Stream 10 e exige x86-64-v3 (AVX2), que o Xeon L5640 da VPS não tem: o gerador
# sai de builder/Containerfile (o mesmo programa, em cima do Fedora). Depois de instalado, o PC
# segue ghcr.io/fernandaoludke/arrumo-os:latest (disk_config/iso.toml): é o GitHub
# Actions que publica as atualizações, a ISO daqui é só a porta de entrada.
set -euo pipefail
cd "$(dirname "$0")"

IMAGEM=localhost/arrumo-os:latest
SAIDA=$PWD/output
DESTINO=/home/fernandao/Site/arrumo-seu-pc/backend/downloads
BIB=localhost/arrumo-bib:latest
# O gerador procura repositório pelo ID do os-release ("bazzite-45") e não acha: os pacotes
# do instalador vêm do Fedora da base (VERSION_ID). Mudou o Fedora do Bazzite, muda aqui.
FEDORA=https://dl.fedoraproject.org/pub/fedora/linux

if [[ "${1:-}" != "--so-iso" ]]; then
echo "== 1/4 build da imagem"
DOCKER_BUILDKIT=1 docker build -t "$IMAGEM" -f Containerfile .
[[ "${1:-}" == "--so-imagem" ]] && exit 0

echo "== 2/4 imagem → storage do podman"
# skopeo 1.4 (Ubuntu 22.04) não fala a API do Docker atual: vai por um tar
sudo rm -rf "$SAIDA" && mkdir -p "$SAIDA"
docker save -o "$SAIDA/imagem.tar" "$IMAGEM"
sudo skopeo copy "docker-archive:$SAIDA/imagem.tar" "containers-storage:$IMAGEM"
rm -f "$SAIDA/imagem.tar"
else
sudo rm -rf "$SAIDA" && mkdir -p "$SAIDA"
fi

echo "== 3/4 ISO (bootc-image-builder, demora)"
sudo podman build -q -t "$BIB" builder/ >/dev/null
sudo podman run --rm --privileged \
    --security-opt label=type:unconfined_t \
    -v "$PWD/disk_config/iso.toml:/config.toml:ro" \
    -v "$SAIDA:/output" \
    -v /var/lib/containers/storage:/var/lib/containers/storage \
    "$BIB" --type anaconda-iso --rootfs btrfs \
    --force-repo "$FEDORA/releases/45/Everything/x86_64/os/" \
    --force-repo "$FEDORA/updates/45/Everything/x86_64/" \
    "$IMAGEM"

ISO=$(sudo find "$SAIDA" -name '*.iso' | head -1)
[[ -n "$ISO" ]] || { echo "ISO não saiu"; exit 1; }

echo "== 4/4 publica no sistema"
mkdir -p "$DESTINO"
sudo install -o "$(id -u)" -g "$(id -g)" -m 644 "$ISO" "$DESTINO/Arrumo-OS.iso.novo"
mv "$DESTINO/Arrumo-OS.iso.novo" "$DESTINO/Arrumo-OS.iso"
SHA=$(sha256sum "$DESTINO/Arrumo-OS.iso" | cut -d' ' -f1)
python3 - "$DESTINO" "$SHA" <<'EOF'
import json, os, sys, datetime
dest, sha = sys.argv[1], sys.argv[2]
info = {"data": datetime.date.today().strftime("%d/%m/%Y"), "sha256": sha,
        "tamanho": os.path.getsize(os.path.join(dest, "Arrumo-OS.iso"))}
json.dump(info, open(os.path.join(dest, "arrumo-os.json"), "w"))
print(info)
EOF
sudo rm -rf "$SAIDA"
echo "Pronto: /diagnosticos → botão Arrumo-OS"
