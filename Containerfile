# Arrumo-OS — Bazzite (Fedora atômico, KDE, pronto para jogo) com a cara da Arrumo Seu PC.
# Duas imagens do mesmo Containerfile (o Actions monta as duas):
#   arrumo-os         base bazzite:stable              AMD/Intel   (ARRUMO_VARIANTE=amd)
#   arrumo-os-nvidia  base bazzite-nvidia-open:stable  GTX 16xx/RTX (ARRUMO_VARIANTE=nvidia)
# A ISO é uma só; no primeiro boot o arrumo-gpu.service troca para a imagem da placa.
ARG BASE_IMAGE=ghcr.io/ublue-os/bazzite:stable

FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files

FROM ${BASE_IMAGE}
ARG ARRUMO_VARIANTE=amd

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    ARRUMO_VARIANTE=${ARRUMO_VARIANTE} /ctx/build.sh

RUN bootc container lint
