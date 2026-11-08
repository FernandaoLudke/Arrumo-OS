# Arrumo-OS — Bazzite (Fedora atômico, KDE, pronto para jogo) com a cara da Arrumo Seu PC.
# bazzite:stable = AMD/Intel; para NVIDIA (GTX 16xx/RTX) trocar por bazzite-nvidia-open:stable.
ARG BASE_IMAGE=ghcr.io/ublue-os/bazzite:stable

FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files

FROM ${BASE_IMAGE}

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/build.sh

RUN bootc container lint
