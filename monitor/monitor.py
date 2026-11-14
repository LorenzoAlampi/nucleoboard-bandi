#!/usr/bin/env python3
"""Controlla le pagine elencate in pagine.json e segnala i link nuovi.

Usa solo la libreria standard di Python. Ogni giorno confronta i link trovati
con quelli visti la volta prima. Un link nuovo su una pagina di bandi è il
segnale più affidabile che sia uscito qualcosa.

Scrive:
  monitor/state.json  cosa è stato visto (si committa)
  novita.json         storico delle novità mostrato dal sito (si committa)
  report.md           testo della segnalazione GitHub (solo se c'è una novità)
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

ROOT = os.environ.get("BANDI_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGINE = os.path.join(ROOT, "monitor", "pagine.json")
STATE = os.path.join(ROOT, "monitor", "state.json")
NOVITA = os.path.join(ROOT, "novita.json")
REPORT = os.path.join(ROOT, "report.md")

UA = "Mozilla/5.0 (compatible; BandiNucleoBoard/1.0)"
PAROLE = re.compile(r"band|avvis|contribut|call|linee[- ]guida|scadenz|finanz|candidat|domand|invito", re.I)
MAX_NOVITA = 200
MAX_VISTI = 3000
MAX_ALTRI_PER_PAGINA = 15
SALTA = {"script", "style", "noscript", "svg"}


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.testo = []
        self.link = {}
        self._href = None
        self._etichetta = []

    def handle_starttag(self, tag, attrs):
        if tag in SALTA:
            self.skip += 1
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._etichetta = []

    def handle_endtag(self, tag):
        if tag in SALTA and self.skip:
            self.skip -= 1
        if tag == "a" and self._href:
            etichetta = " ".join("".join(self._etichetta).split())
            if self._href not in self.link or (etichetta and not self.link[self._href]):
                self.link[self._href] = etichetta
            self._href = None

    def handle_data(self, data):
        if self.skip:
            return
        self.testo.append(data)
        if self._href is not None:
            self._etichetta.append(data)


def scarica(url):
    richiesta = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "it,en;q=0.5"})
    with urllib.request.urlopen(richiesta, timeout=30) as r:
        grezzo = r.read(3_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
    return grezzo.decode(charset, errors="replace")


def analizza(url, html):
    p = Parser()
    p.feed(html)
    link = {}
    for href, etichetta in p.link.items():
        assoluto = urldefrag(urljoin(url, href.strip()))[0]
        if urlparse(assoluto).scheme not in ("http", "https"):
            continue
        if assoluto.rstrip("/") == url.rstrip("/"):
            continue
        if assoluto not in link or (etichetta and not link[assoluto]):
            link[assoluto] = etichetta
    testo = " ".join(" ".join(p.testo).split())
    return link, hashlib.sha256(testo.encode("utf-8")).hexdigest()


def carica(percorso, default):
    try:
        with open(percorso, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def salva(percorso, dati):
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
        f.write("\n")


def etichetta_link(url, etichetta):
    if etichetta:
        return etichetta[:140]
    return os.path.basename(urlparse(url).path.rstrip("/")) or url


def main():
    oggi = date.today().isoformat()
    pagine = carica(PAGINE, [])
    stato = carica(STATE, {})
    novita = carica(NOVITA, [])

    nuove_probabili = []   # (pagina, titolo, url)
    nuovi_altri = {}       # pagina -> [(titolo, url)]
    testo_cambiato = []    # (pagina, url)
    problemi = []          # (pagina, url, errore)
    prima_volta = 0

    for pagina in pagine:
        nome, url = pagina["nome"], pagina["url"]
        vecchio = stato.get(url, {})
        try:
            html = scarica(url)
            link, impronta = analizza(url, html)
        except Exception as e:  # rete, 403, timeout: si segnala una sola volta
            messaggio = f"{type(e).__name__}: {e}"[:200]
            if not vecchio.get("errore"):
                problemi.append((nome, url, messaggio))
            vecchio["errore"] = messaggio
            stato[url] = vecchio
            print(f"[errore] {nome}: {messaggio}")
            continue

        visti = vecchio.get("visti")
        if visti is None:
            # prima lettura: si memorizza tutto senza segnalare
            prima_volta += 1
            stato[url] = {"visti": sorted(link)[:MAX_VISTI], "hash": impronta, "controllato": oggi}
            print(f"[base] {nome}: {len(link)} link memorizzati")
            continue

        visti_set = set(visti)
        nuovi = [(u, e) for u, e in link.items() if u not in visti_set]
        for u, e in nuovi:
            titolo = etichetta_link(u, e)
            if PAROLE.search(f"{e} {u}"):
                nuove_probabili.append((nome, titolo, u))
            else:
                nuovi_altri.setdefault(nome, []).append((titolo, u))

        if pagina.get("controlla_testo") and vecchio.get("hash") and vecchio["hash"] != impronta:
            testo_cambiato.append((nome, url))

        stato[url] = {
            "visti": (visti + [u for u, _ in nuovi])[-MAX_VISTI:],
            "hash": impronta,
            "controllato": oggi,
        }
        print(f"[ok] {nome}: {len(nuovi)} link nuovi")

    salva(STATE, stato)

    if not (nuove_probabili or nuovi_altri or testo_cambiato or problemi):
        if prima_volta:
            print(f"Prima esecuzione: memorizzate {prima_volta} pagine. Nessuna segnalazione.")
        else:
            print("Nessuna novità.")
        return

    # storico mostrato dal sito: solo le novità che contano
    nuove_voci = []
    for nome, titolo, u in nuove_probabili:
        nuove_voci.append({"data": oggi, "pagina": nome, "titolo": titolo, "url": u, "tipo": "link"})
    for nome, u in testo_cambiato:
        nuove_voci.append({"data": oggi, "pagina": nome, "titolo": "Il testo della pagina è cambiato", "url": u, "tipo": "testo"})
    if nuove_voci:
        salva(NOVITA, (nuove_voci + novita)[:MAX_NOVITA])

    righe = [f"# Novità bandi del {oggi}", ""]
    if nuove_probabili:
        righe += ["## Link nuovi che sembrano bandi", ""]
        for nome, titolo, u in nuove_probabili:
            righe.append(f"- **{titolo}** ({nome}): {u}")
        righe.append("")
    if testo_cambiato:
        righe += ["## Pagine il cui testo è cambiato", ""]
        for nome, u in testo_cambiato:
            righe.append(f"- {nome}: {u}")
        righe.append("")
    if nuovi_altri:
        righe += ["## Altri link nuovi (possono essere rumore)", ""]
        for nome, voci in nuovi_altri.items():
            righe.append(f"**{nome}**")
            for titolo, u in voci[:MAX_ALTRI_PER_PAGINA]:
                righe.append(f"- {titolo}: {u}")
            if len(voci) > MAX_ALTRI_PER_PAGINA:
                righe.append(f"- e altri {len(voci) - MAX_ALTRI_PER_PAGINA}")
            righe.append("")
    if problemi:
        righe += ["## Pagine non raggiungibili", ""]
        for nome, u, errore in problemi:
            righe.append(f"- {nome} ({u}): {errore}")
        righe.append("")
    righe.append("Quando leggi una novità interessante, aggiungi il bando in `bandi.json`.")
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(righe) + "\n")
    print("Segnalazione scritta in report.md")


if __name__ == "__main__":
    main()
    sys.exit(0)
