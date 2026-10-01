# Hüttenfinder

Freie Betten auf Alpenvereinshütten, live von hut-reservation.org. Die Seite ist statisch und lädt sofort;
ein geplanter Job holt die Daten alle 3 Stunden.

## Online stellen (GitHub Pages, kostenlos)
1. Öffentliches Repository anlegen und diesen Ordner hochladen:
   `git init -b main && git add . && git commit -m "Hüttenfinder" && gh repo create huettenfinder --public --source=. --push`
2. Im Repository: Settings > Pages > Source: **GitHub Actions**.
3. Tab Actions > "Daten aktualisieren und veröffentlichen" > Run workflow.
   Der erste Lauf dauert ca. 20 Minuten (Verfügbarkeit plus OpenStreetMap-Daten). Danach ist die Seite unter
   `https://<dein-name>.github.io/huettenfinder/` erreichbar und aktualisiert sich selbst.

## Lokal ausprobieren
`python3 scripts/update.py && python3 -m http.server 8000 --directory site`, dann http://localhost:8000

## Daten
- Verfügbarkeit: hut-reservation.org (`getHutAvailability`), schonend gedrosselt.
- Hüttenverzeichnis `site/huetten.json`: Datensatz severin-kacianka/alpine_hut (CC0), 547 Hütten.
- Freie Nacht fürs Klima: Teilnehmerliste auf alpenverein.de/freie-nacht (Stand 23.09.2026) in `site/attribute.json`.
- Verpflegung: `veg_komplett` und `veg_option` in `site/attribute.json` (aus Alpenverein-Bericht und 1000things) plus
  OpenStreetMap-Tags `diet:vegetarian` und `diet:vegan`. Nicht vollständig.
- Öffentlich erreichbar: Luftlinie zur nächsten Bus- oder Bahnhaltestelle bis 5 km, berechnet aus OpenStreetMap.

## Hinweise
- GitHub pausiert geplante Workflows nach 60 Tagen ohne Aktivität im Repository.
- Blockiert hut-reservation.org die GitHub-Server (HTTP 403 im Log), `scripts/update.py` lokal ausführen
  und den Ordner `site/` bei einem Hoster wie Netlify oder Cloudflare Pages hochladen.
