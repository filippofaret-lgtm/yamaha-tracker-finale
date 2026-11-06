import json, os, re, datetime, urllib.request, urllib.parse

API_KEY = os.environ["SERPAPI_KEY"]
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID")
BUDGET = 800
OUT = "docs/prices.json"

GUITARS = [
    {"id": "llta", "name": "Yamaha LLTA", "query": "Yamaha LLTA chitarra acustica", "must": "llta"},
    {"id": "fgta", "name": "Yamaha FGTA", "query": "Yamaha FGTA chitarra acustica", "must": "fgta"},
    {"id": "tag1e", "name": "Yamaha TAG1E", "query": "Yamaha TAG1E chitarra", "must": "tag1e"},
    {"id": "ll16", "name": "Yamaha LL16", "query": "Yamaha LL16 chitarra acustica", "must": "ll16"},
]
BAD = ["custodia", "corde", "cover", "capotasto", "tracolla", "plettri", "borsa", "gigbag", "supporto",
       "12 string", "12-string", "12 corde"]
MIN_PRICE = 150  # scarta accessori
EXCLUDE_STORES = ["reverb", "ray's midbell"]  # negozi esteri/usato: togli dalla lista per includerli


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def search(query):
    params = urllib.parse.urlencode({
        "engine": "google_shopping", "q": query, "gl": "it", "hl": "it",
        "google_domain": "google.it", "api_key": API_KEY,
    })
    with urllib.request.urlopen("https://serpapi.com/search.json?" + params, timeout=60) as r:
        return json.load(r).get("shopping_results", [])


def offers_for(g):
    out = []
    for r in search(g["query"]):
        title = r.get("title", "")
        price = r.get("extracted_price")
        if price is None or price < MIN_PRICE or g["must"] not in norm(title):
            continue
        if any(b in title.lower() for b in BAD):
            continue
        if any(x in r.get("source", "").lower() for x in EXCLUDE_STORES):
            continue
        out.append({
            "store": r.get("source", "?"), "title": title, "price": price,
            "link": r.get("link") or r.get("product_link", ""),
        })
    out.sort(key=lambda o: o["price"])
    return out[:8]


def notify(text):
    if not (TG_TOKEN and TG_CHAT):
        return
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)


def main():
    old = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = {g["id"]: g for g in json.load(f).get("guitars", [])}
    today = datetime.date.today().isoformat()
    result = []
    for g in GUITARS:
        prev = old.get(g["id"], {})
        history = [h for h in prev.get("history", []) if h["date"] != today]
        try:
            offers = offers_for(g)
        except Exception as e:
            print("Errore", g["name"], e)
            offers = prev.get("offers", [])
            result.append({**prev, "id": g["id"], "name": g["name"], "offers": offers,
                           "min": prev.get("min"), "history": history})
            continue
        low = offers[0]["price"] if offers else None
        last = history[-1]["min"] if history else None
        if low is not None:
            history.append({"date": today, "min": low})
            if low <= BUDGET and (last is None or low < last):
                notify(f"{g['name']}: {low:.0f} € da {offers[0]['store']}\n{offers[0]['link']}")
        result.append({"id": g["id"], "name": g["name"], "offers": offers, "min": low, "history": history})
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.datetime.utcnow().isoformat() + "Z", "budget": BUDGET, "guitars": result},
                  f, ensure_ascii=False, indent=1)


main()
