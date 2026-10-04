"""Text normalisation so script text and Whisper output compare token-by-token."""
from __future__ import annotations

import re
import unicodedata

_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}|<[^>]*>")
_THOUSANDS = re.compile(r"(?<=\d)[,.](?=\d{3}(?!\d))")
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num_words(n: int) -> list[str]:
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        t, o = divmod(n, 10)
        return [_TENS[t]] + ([_ONES[o]] if o else [])
    if n < 1000:
        h, r = divmod(n, 100)
        return [_ONES[h], "hundred"] + (num_words(r) if r else [])
    if n < 1_000_000:
        th, r = divmod(n, 1000)
        return num_words(th) + ["thousand"] + (num_words(r) if r else [])
    return [str(n)]


def clean_cue_text(text: str) -> str:
    """Drop stage directions like (pause) or [music] from script lines."""
    return _BRACKETS.sub(" ", text)


def tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text).lower().replace("\u2019", "'").replace("'", "")
    t = _THOUSANDS.sub("", t)
    out: list[str] = []
    for tok in _TOKEN.findall(t):
        if tok.isdigit() and len(tok) <= 6:
            out.extend(num_words(int(tok)))
        else:
            out.append(tok)
    return out
