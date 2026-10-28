"""Tokenizer for GeoGebra-style input.

Handles unicode operators (π, °, ², √, ≤, ≠, ∧, ∨, ¬, ⊗, −, ·, ×, ÷), labels with
subscripts (``A_1``, ``a_{max}``) and primes (``A'``), strings with escapes, and
scientific notation (``1e-3``; ``2e`` alone is 2·e).
"""

from __future__ import annotations

from pykaufgeo.core.errors import ParseError
from pykaufgeo.parser.tokens import T, Token

MAX_INPUT = 100_000

SUPERSCRIPT_DIGITS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                      "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}
SUPERSCRIPT_MINUS = "⁻"

# Multi-character operators first; values are canonical spellings.
MULTI_OPS = {
    ":=": (T.ASSIGN, ":="),
    "==": (T.OP, "=="),
    "!=": (T.OP, "!="),
    "<=": (T.OP, "<="),
    ">=": (T.OP, ">="),
    "&&": (T.OP, "and"),
}
SINGLE = {
    "+": (T.OP, "+"), "-": (T.OP, "-"), "−": (T.OP, "-"), "–": (T.OP, "-"),
    "*": (T.OP, "*"), "·": (T.OP, "*"), "×": (T.OP, "*"), "⋅": (T.OP, "*"),
    "/": (T.OP, "/"), "÷": (T.OP, "/"), "^": (T.OP, "^"),
    "=": (T.OP, "="), "<": (T.OP, "<"), ">": (T.OP, ">"),
    "≤": (T.OP, "<="), "≥": (T.OP, ">="), "≠": (T.OP, "!="), "≟": (T.OP, "=="),
    "∧": (T.OP, "and"), "∨": (T.OP, "or"), "¬": (T.OP, "not"), "⊕": (T.OP, "xor"),
    "!": (T.OP, "!"), "°": (T.OP, "°"), "%": (T.OP, "%"), "⊗": (T.OP, "cross"),
    "√": (T.OP, "√"), "∈": (T.OP, "in"),
    "(": (T.LPAREN, "("), ")": (T.RPAREN, ")"),
    "[": (T.LBRACKET, "["), "]": (T.RBRACKET, "]"),
    "{": (T.LBRACE, "{"), "}": (T.RBRACE, "}"),
    ",": (T.COMMA, ","), ";": (T.SEMI, ";"), ":": (T.COLON, ":"),
    "|": (T.PIPE, "|"), "?": (T.QUESTION, "?"),
}
SPECIAL_IDENTS = {"∞": "∞", "ℯ": "ℯ", "π": "π", "ί": "ί"}
QUOTES = {'"': '"', "“": "”", "”": "”"}


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() and ch not in SUPERSCRIPT_DIGITS


def _is_ident_char(ch: str) -> bool:
    return (ch.isalnum() and ch not in SUPERSCRIPT_DIGITS) or ch == "$"


def tokenize(text: str) -> list[Token]:
    if len(text) > MAX_INPUT:
        raise ParseError(f"Input is too long ({len(text)} characters; the limit is {MAX_INPUT}).")
    tokens: list[Token] = []
    i, n = 0, len(text)
    space = False
    while i < n:
        ch = text[i]
        if ch.isspace():
            space = True
            i += 1
            continue
        start = i
        # ---- numbers ----------------------------------------------------------
        if ch.isdigit() and ch not in SUPERSCRIPT_DIGITS or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            while i < n and text[i].isdigit() and text[i] not in SUPERSCRIPT_DIGITS:
                i += 1
            if i < n and text[i] == "." and not (i + 1 < n and text[i + 1] == "."):
                i += 1
                while i < n and text[i].isdigit() and text[i] not in SUPERSCRIPT_DIGITS:
                    i += 1
            if i < n and text[i] in "eE":
                j = i + 1
                if j < n and text[j] in "+-":
                    j += 1
                if j < n and text[j].isdigit() and text[j] not in SUPERSCRIPT_DIGITS:
                    while j < n and text[j].isdigit() and text[j] not in SUPERSCRIPT_DIGITS:
                        j += 1
                    i = j
            tokens.append(Token(T.NUMBER, text[start:i], start, space))
            space = False
            continue
        # ---- superscript exponents -------------------------------------------
        if ch in SUPERSCRIPT_DIGITS or ch == SUPERSCRIPT_MINUS:
            neg = False
            if ch == SUPERSCRIPT_MINUS:
                neg = True
                i += 1
            digits = ""
            while i < n and text[i] in SUPERSCRIPT_DIGITS:
                digits += SUPERSCRIPT_DIGITS[text[i]]
                i += 1
            if not digits:
                raise ParseError(f"Superscript minus without digits at position {start + 1}.", start)
            tokens.append(Token(T.OP, "^", start, space))
            if neg:
                tokens.append(Token(T.OP, "-", start, False))
            tokens.append(Token(T.NUMBER, digits, start, False))
            space = False
            continue
        # ---- identifiers ------------------------------------------------------
        if ch == "$":  # CAS row reference: $3 is the output of row 3, $ the previous row
            i += 1
            while i < n and text[i].isdigit():
                i += 1
            tokens.append(Token(T.IDENT, text[start:i], start, space))
            space = False
            continue
        if ch in SPECIAL_IDENTS:
            tokens.append(Token(T.IDENT, SPECIAL_IDENTS[ch], start, space))
            i += 1
            space = False
            continue
        if _is_ident_start(ch):
            i += 1
            while i < n and _is_ident_char(text[i]) and text[i] not in SPECIAL_IDENTS:
                i += 1
            name = text[start:i]
            if i < n and text[i] == "_":
                if i + 1 < n and text[i + 1] == "{":
                    close = text.find("}", i + 2)
                    if close < 0:
                        raise ParseError(f"Missing '}}' in subscript at position {i + 1}.", i)
                    sub = text[i + 2:close].strip()
                    if not sub or not all(_is_ident_char(c) for c in sub):
                        raise ParseError(f"Invalid subscript '{sub}' at position {i + 1}.", i)
                    name += f"_{sub}" if len(sub) == 1 else f"_{{{sub}}}"
                    i = close + 1
                elif i + 1 < n and _is_ident_char(text[i + 1]):
                    name += "_" + text[i + 1]
                    i += 2
                else:
                    raise ParseError(f"Subscript '_' must be followed by a letter or digit (position {i + 1}).", i)
            while i < n and text[i] in "'′":
                name += "'"
                i += 1
            tokens.append(Token(T.IDENT, name, start, space))
            space = False
            continue
        # ---- strings ----------------------------------------------------------
        if ch in QUOTES:
            close_q = QUOTES[ch]
            i += 1
            buf = []
            while i < n and text[i] != close_q and not (close_q == '"' and text[i] == "”"):
                if text[i] == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
                    i += 2
                    continue
                buf.append(text[i])
                i += 1
            if i >= n:
                raise ParseError(f"Text starting at position {start + 1} is missing its closing quote.", start)
            i += 1
            tokens.append(Token(T.STRING, "".join(buf), start, space))
            space = False
            continue
        # ---- operators and punctuation ---------------------------------------
        two = text[i:i + 2]
        if two in MULTI_OPS:
            tt, val = MULTI_OPS[two]
            tokens.append(Token(tt, val, start, space))
            i += 2
            space = False
            continue
        if ch in SINGLE:
            tt, val = SINGLE[ch]
            tokens.append(Token(tt, val, start, space))
            i += 1
            space = False
            continue
        if ch == "'":
            raise ParseError(f"Unexpected ' at position {start + 1} (primes follow a name, as in f').", start)
        raise ParseError(f"Unexpected character '{ch}' at position {start + 1}.", start)
    tokens.append(Token(T.EOF, "", n, space))
    return tokens
