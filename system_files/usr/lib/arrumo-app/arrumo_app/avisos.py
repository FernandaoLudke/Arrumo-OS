"""Mesma régua do `Coleta/Avisos.cs` do Arrumo-App de Windows, com o texto ajustado
para o Arrumo-OS. Cada aviso diz o problema e o que fazer, sem sigla."""

ORDEM = ("critico", "atencao", "info")


def gerar(r):
    a = []

    def add(nivel, titulo, detalhe):
        a.append({"nivel": nivel, "titulo": titulo, "detalhe": detalhe})

    for d in r.get("discos") or []:
        nome = d.get("modelo") or "disco"
        if d.get("saude") == "Ruim":
            add("critico", f"{nome} com falha",
                "O próprio disco se declarou defeituoso. Faça backup dos seus arquivos agora e troque o disco antes que ele pare de vez.")
        elif d.get("saude") == "Atenção":
            add("atencao", f"{nome} dando sinais de problema",
                "O disco registrou setores ruins. Vale fazer backup e uma avaliação antes que vire perda de arquivos.")
        gasto = d.get("desgaste_pct")
        if gasto is not None and gasto >= 90:
            add("critico", f"SSD {nome} no fim da vida ({gasto}% de desgaste)",
                "A vida útil de gravação do SSD está quase no fim. Faça backup e planeje a troca.")
        elif gasto is not None and gasto >= 70:
            add("atencao", f"SSD {nome} com {gasto}% de desgaste",
                "Ainda funciona, mas já gastou boa parte da vida útil. Bom momento para garantir o backup.")
        temp = d.get("temperatura_c")
        if temp is not None and temp >= 70:
            add("atencao", f"{nome} esquentando ({temp} °C)",
                "Disco quente perde desempenho e vida útil. Pode ser falta de ventilação ou de dissipador no SSD.")
        if d.get("sistema") and d.get("tipo") == "HD":
            add("atencao", "Sistema instalado em HD mecânico",
                "É o maior motivo de PC lento e de jogo demorando para carregar. Um SSD deixa tudo várias vezes mais rápido.")

    for v in r.get("volumes") or []:
        if v["total_gb"] > 0 and v["livre_gb"] / v["total_gb"] < 0.10:
            raiz = v["letra"] in ("/", "/var", "/var/home", "/home")
            add("atencao" if raiz else "info", f"Disco {v['letra']} quase cheio ({v['livre_gb']:.0f} GB livres)",
                "Com pouco espaço o sistema não consegue se atualizar e jogo novo não instala." if raiz
                else "Pouco espaço livre nesta unidade.")

    mem = r.get("memoria") or {}
    total = mem.get("total_gb") or 0
    if 0 < total < 7.5:
        gb = f"{total:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        add("atencao", f"Pouca memória: {gb} GB",
            "Para jogar e manter o navegador aberto, o mínimo confortável é 8 GB — 16 GB para jogos atuais. Aumentar a memória é um upgrade barato e de efeito imediato.")
    modulos = mem.get("modulos") or []
    lentos = [m for m in modulos if m.get("velocidade") and m.get("velocidade_atual")
              and m["velocidade_atual"] < m["velocidade"] - 100]
    if lentos:
        m = lentos[0]
        add("atencao", "Memória rodando abaixo da velocidade",
            f"O pente é de {m['velocidade']} MT/s e está trabalhando a {m['velocidade_atual']} MT/s. Normalmente é o perfil XMP/EXPO desligado na BIOS — ativar devolve o desempenho que você pagou.")
    if len(modulos) == 1 and (mem.get("slots") or 0) >= 2:
        add("info", "Memória em canal simples",
            "Só um pente instalado e há slot livre. Com dois pentes iguais a memória trabalha em dual channel, o que ajuda bastante em jogos e no vídeo integrado.")

    saude = (r.get("bateria") or {}).get("saude_pct")
    if saude is not None:
        if saude < 40:
            add("critico", f"Bateria gasta ({saude}% da capacidade original)",
                "A bateria segura menos da metade da carga de quando era nova. A troca devolve a autonomia do notebook.")
        elif saude < 70:
            add("atencao", f"Bateria com {saude}% da capacidade original",
                "Já perdeu boa parte da autonomia. Se o notebook desliga rápido fora da tomada, é ela.")

    if not r.get("admin"):
        add("info", "Saúde dos discos não foi lida",
            "A leitura do SMART e dos pentes de memória precisa de permissão. Abra o Arrumo-App de novo e autorize quando ele pedir.")

    return sorted(a, key=lambda x: ORDEM.index(x["nivel"]))
