# Arrumo-OS

Sistema para PC gamer leve, da Arrumo Seu PC: o **Bazzite** (Fedora atômico com KDE, Steam,
Proton, Gamemode e MangoHud prontos) com a nossa cara por cima.

O que muda em relação ao Bazzite:

- **Arrumo-App para Linux** (`system_files/usr/lib/arrumo-app/`, Python + Qt 6): Diagnóstico com o
  mesmo relatório online do app de Windows (`POST /api/diagnostico` → `/d/<token>`, mesmo JSON do
  `Relatorio.cs`), Sensores (hwmon ao vivo) e Leveza (RAM/CPU em repouso, quem mais gasta, opções
  de inicialização da Steam). O que só o root lê (SMART, pentes, série) vem de
  `/usr/libexec/arrumo-app/coleta-root` via `pkexec`, liberado sem senha para a sessão local
  (`br.com.arrumoseupc.app.policy`). `arrumo-app --json` imprime o relatório sem abrir janela.
- **Chrome** e outros Flatpaks da lista `/usr/share/arrumo-os/flatpaks`, instalados no primeiro boot
  pelo `arrumo-flatpaks.service` (de novo quando a lista muda). O RPM do Chrome não entra na
  imagem porque escreve em `/opt`.
- Papel de parede aplicado uma vez por usuário (`/usr/libexec/arrumo-os/primeiro-login`) e
  `PRETTY_NAME` "Arrumo-OS". `ID`/`VARIANT_ID` continuam do Bazzite — o `ujust` e o atualizador
  dependem deles.

## Como se atualiza

O GitHub Actions (`.github/workflows/build.yml`) gera a imagem todo dia e publica em
`ghcr.io/fernandaoludke/arrumo-os:latest`. PC instalado puxa de lá sozinho (a ISO faz o
`bootc switch` para esse endereço no fim da instalação). Deu ruim numa versão: no boot,
escolher a entrada anterior — o sistema volta como estava.

Para quem já tem Bazzite instalado, sem ISO:

```bash
sudo bootc switch ghcr.io/fernandaoludke/arrumo-os:latest
```

## Gerar a ISO (na VPS)

```bash
./gerar-iso.sh              # build + ISO + publica em /diagnosticos (botão Arrumo-OS, só admin)
./gerar-iso.sh --so-imagem  # só o build, para testar o Containerfile
```

## NVIDIA

O Actions publica duas imagens do mesmo Containerfile: `arrumo-os` (base `bazzite`, AMD/Intel)
e `arrumo-os-nvidia` (base `bazzite-nvidia-open`, GTX 16xx / RTX). A ISO é uma só e instala a de
AMD/Intel; no primeiro boot o `arrumo-gpu.service` vê se há placa NVIDIA e troca para a outra
(`bootc switch`), reiniciando sozinho se ninguém estiver logado — senão entra no próximo boot.

A ISO sai da VPS (`./gerar-iso.sh`, ou `--so-iso` reaproveitando a imagem). O
bootc-image-builder oficial exige CPU x86-64-v3 e o Xeon da VPS não tem: o gerador é o de
`builder/` (o mesmo programa, em cima do Fedora).

## Anticheat

CS2 (matchmaking/Premier/VAC) roda nativo. GamersClub, FACEIT, Valorant, LoL e Fortnite **não**
rodam no Linux — para esses, dual boot com Windows.
