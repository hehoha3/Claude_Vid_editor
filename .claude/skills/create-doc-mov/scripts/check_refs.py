"""Verify research anchors before they go into a screenplay: one compact line per DOI or search query.

usage: python check_refs.py 10.1002/ecy.3286 10.1007/s00442-007-0764-5 ["jaguar arboreal flooded forest"] [--abstract]
A DOI prints authors, year, journal, volume/pages and title (Crossref); a quoted query prints the 3 best Crossref
matches. --abstract adds the first 600 characters of the abstract (Europe PMC, then Semantic Scholar) so a sentence
that depends on a number can be checked against the source. Prints NOT FOUND instead of guessing.
"""
import json
import re
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "create-doc-mov/1.0 (reference check)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def line(m):
    au = ", ".join(a.get("family", "") for a in m.get("author", [])[:4]) + (" et al." if len(m.get("author", [])) > 4 else "")
    year = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    return (f"{m['DOI']} | {au} ({year}) | {(m.get('container-title') or [''])[0]} {m.get('volume', '')} "
            f"{m.get('page', '')} | {(m.get('title') or [''])[0]}")


def abstract(doi):
    try:
        r = get("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&query=DOI:%22"
                + urllib.parse.quote(doi) + "%22")["resultList"]["result"]
        if r and r[0].get("abstractText"):
            return r[0]["abstractText"]
    except Exception:
        pass
    try:
        return get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract").get("abstract") or ""
    except Exception:
        return ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    want_abs = "--abstract" in sys.argv
    for arg in [a for a in sys.argv[1:] if a != "--abstract"]:
        try:
            if re.match(r"^10\.\d{4,}/", arg):
                m = get("https://api.crossref.org/works/" + urllib.parse.quote(arg))["message"]
                print(line(m))
                if want_abs:
                    a = re.sub(r"<[^>]+>|\s+", " ", abstract(arg)).strip()
                    print("   abstract:", a[:600] or "none available")
            else:
                print(f"-- {arg}")
                q = "https://api.crossref.org/works?rows=3&select=DOI,title,author,container-title,issued,volume,page&query.bibliographic="
                for m in get(q + urllib.parse.quote(arg))["message"]["items"]:
                    print("  ", line(m))
        except Exception as e:
            print(f"{arg} | NOT FOUND ({e.__class__.__name__})")


if __name__ == "__main__":
    main()
