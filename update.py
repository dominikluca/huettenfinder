#!/usr/bin/env python3
"""Hüttenfinder: Daten-Update (nur Standardbibliothek).

Schreibt site/data/availability.json (Live-Verfügbarkeit von hut-reservation.org) und, falls
älter als 14 Tage oder mit --osm, site/data/attribute_osm.json (Haltestellen und Verpflegung
aus OpenStreetMap). Aufruf, Header und Drosselung folgen dem Referenzprojekt
severin-kacianka/alpine_hut (CC0).

    python3 scripts/update.py          # Verfügbarkeit, dauert ca. 10 Minuten
    python3 scripts/update.py --osm    # OSM-Daten erzwingen
"""
import json, math, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, timedelta

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
DATA = os.path.join(SITE, "data")
API = "https://www.hut-reservation.org/api/v1/reservation/getHutAvailability?hutId={}&step=WIZARD"
OVERPASS = "https://overpass-api.de/api/interpreter"
HDR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
       "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"}


def schreiben(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))


def frisch(name, tage=14):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return time.time() - json.load(f)["t"] < tage * 86400
    except Exception:
        return False


def kompakt(tage):
    """{Datum: freie Betten oder -1} -> {"s": Starttag, "f": [freie Betten je Tag]}"""
    ds = sorted(tage)
    start = date.fromisoformat(ds[0])
    n = (date.fromisoformat(ds[-1]) - start).days + 1
    return {"s": ds[0], "f": [tage.get((start + timedelta(i)).isoformat(), -1) for i in range(n)]}


def abrufen(hid):
    try:
        with urllib.request.urlopen(urllib.request.Request(API.format(hid), headers=HDR), timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None


def verfuegbarkeit(huts):
    out, ok, gedrosselt = {}, 0, 0
    for h in huts:
        try:
            code, data = abrufen(h["id"])
        except Exception as e:
            print("Fehler", h["id"], e)
            time.sleep(5)
            continue
        if code == 200 and isinstance(data, list):
            tage = {}
            for t in data:
                f = str(t.get("dateFormatted") or "")
                d = f"{f[6:10]}-{f[3:5]}-{f[:2]}" if len(f) == 10 and f[2] == "." else str(t.get("date") or "")[:10]
                zu = str(t.get("hutStatus") or "").upper() == "CLOSED"
                frei = t.get("freeBeds")
                if len(d) == 10:
                    tage[d] = -1 if zu or frei is None else int(frei)
            if tage:
                out[str(h["id"])] = kompakt(tage)
            ok += 1
            time.sleep(5 if ok % 10 == 0 else 0.5)   # 0,5 s je Abruf, alle 10 Abrufe 5 s Pause
        else:
            print("HTTP", code, h["id"])
            time.sleep(0.5)
            if code in (403, 429):
                gedrosselt += 1
                time.sleep(5)
                if gedrosselt >= 5:
                    print("Gedrosselt, Abbruch")
                    break
    return out


def overpass(q):
    for versuch in range(3):
        try:
            req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": "Huettenfinder/1.0 (privates Projekt)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("Overpass:", e)
            time.sleep(30 * (versuch + 1))
    return None


def meter(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(x))


def osm(huts):
    """Nächste Bus-/Bahnhaltestelle (bis 5 km Luftlinie) und Verpflegungs-Tags der OSM-Hütte (bis 300 m)."""
    res = {}
    hs = [h for h in huts if h.get("lat") is not None]
    for i in range(0, len(hs), 10):
        gr = hs[i:i + 10]
        q = "[out:json][timeout:90];(" + "".join(
            f'node["highway"="bus_stop"](around:5000,{h["lat"]},{h["lon"]});'
            f'node["railway"~"^(station|halt)$"](around:5000,{h["lat"]},{h["lon"]});' for h in gr) + ");out skel;"
        d = overpass(q)
        if d:
            stops = [(e["lat"], e["lon"]) for e in d.get("elements", []) if "lat" in e]
            for h in gr:
                m = min((meter(h["lat"], h["lon"], a, b) for a, b in stops), default=None)
                if m is not None and m <= 5000:
                    res.setdefault(str(h["id"]), {})["km"] = round(m / 1000, 1)
        time.sleep(3)
        q = "[out:json][timeout:90];(" + "".join(
            f'nwr["tourism"="alpine_hut"](around:300,{h["lat"]},{h["lon"]});' for h in gr) + ");out tags center;"
        d = overpass(q)
        for e in (d or {}).get("elements", []):
            t, c = e.get("tags", {}), (e.get("center") or e)
            if "lat" not in c:
                continue
            vg, vn = t.get("diet:vegetarian"), t.get("diet:vegan")
            wert = "komplett" if "only" in (vg, vn) else "option" if "yes" in (vg, vn) else None
            h = min(gr, key=lambda h: meter(h["lat"], h["lon"], c["lat"], c["lon"]))
            if wert and meter(h["lat"], h["lon"], c["lat"], c["lon"]) <= 300:
                res.setdefault(str(h["id"]), {})["veg"] = wert
        time.sleep(3)
        print(f"OSM: {min(i + 10, len(hs))} von {len(hs)} Hütten")
    return res


def main():
    with open(os.path.join(SITE, "huetten.json"), encoding="utf-8") as f:
        huts = json.load(f)
    os.makedirs(DATA, exist_ok=True)
    av = verfuegbarkeit(huts)
    if len(av) < len(huts) * 0.5:
        sys.exit(f"Nur {len(av)} von {len(huts)} Hütten geladen. Abbruch, alte Daten bleiben erhalten.")
    schreiben("availability.json", {"t": int(time.time()), "huts": av})
    print(f"Verfügbarkeit: {len(av)} Hütten")
    if "--osm" in sys.argv or not frisch("attribute_osm.json"):
        o = osm(huts)
        if o:
            schreiben("attribute_osm.json", {"t": int(time.time()), "huts": o})
            print(f"OSM-Daten: {len(o)} Hütten")


if __name__ == "__main__":
    main()
