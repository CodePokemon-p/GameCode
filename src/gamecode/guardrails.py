"""
guardrails.py — defense-in-depth input safety (8 layers).

Layer overview (applied in order, fail-fast):
  L1  Normalization       — NFKD, homoglyph transliteration, de-leet, whitespace
  L2  Fuzzy injection     — Levenshtein distance against verb/target vocabularies
  L3  Encoding detection  — decode base64/hex/URL/ROT13, re-scan decoded payload
  L4  Regex sentinels     — explicit jailbreak markers, special tokens
  L5  Off-topic           — weather, politics, general knowledge
  L6  Global language     — only C++ and C# allowed anywhere in the input
  L7  Per-agent scope     — Agent1 = C++-only, Agent2 = C#-only, etc.
  L8  Plan-type edit      — plan agents may not edit files or run builds
"""

from __future__ import annotations

import base64
import codecs
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""
    layer: str = ""


# C++/C# detection — \b is wrong here because '#' and '+' are non-word chars.
CPP_PATTERN = re.compile(r"(?<![a-zA-Z0-9])(c\+\+|cpp|cplusplus)(?![a-zA-Z0-9])")
CS_PATTERN  = re.compile(r"(?<![a-zA-Z0-9])(c#|csharp|c-sharp|dotnet)(?![a-zA-Z0-9])")


class Guardrail:
    MAX_INPUT_LEN = 4000
    # Tiered fuzzy tolerance: longer words get more slack, short words none.
    MIN_FUZZY_LEN = 4           # tokens shorter than this: exact match only
    MAX_TOKEN_DIST_SHORT = 1    # tokens 4-5 chars
    MAX_TOKEN_DIST_LONG  = 2    # tokens ≥ 6 chars
    # ---- L1: normalization maps -------------------------------------
    LEET_MAP = str.maketrans({
        "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
        "7": "t", "@": "a", "$": "s", "!": "i", "|": "l",
    })

    # Common Cyrillic / Greek homoglyphs → Latin equivalents.
    # Prevents "ignоrе" (Cyrillic о/е) from bypassing the verb list.
    HOMOGLYPHS = str.maketrans({
        "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p",
        "\u0441": "c", "\u0443": "y", "\u0445": "x", "\u0456": "i",
        "\u0458": "j", "\u0455": "s",
        "\u0410": "A", "\u0415": "E", "\u041e": "O", "\u0420": "P",
        "\u0421": "C", "\u0423": "Y", "\u0425": "X",
        "\u03b1": "a", "\u03b2": "b", "\u03b5": "e", "\u03b9": "i",
        "\u03ba": "k", "\u03bd": "v", "\u03bf": "o", "\u03c1": "p",
        "\u03c4": "t", "\u03c5": "u", "\u03c7": "x",
    })

    # ---- L2: fuzzy injection vocabularies --------------------------
    # Strong verbs — used alone these are harmless, but paired with a
    # target they signal an override attempt.
    VERBS = {
        "ignore", "forget", "disregard", "skip", "bypass", "override",
        "discard", "abandon", "dismiss", "neglect", "suppress", "cancel",
    }
    # Strong targets — words that make the verb suspicious.
    # "rule" / "system" deliberately excluded here — they produce too
    # many false positives in normal C++ talk ("system clock", "style rules").
    TARGETS = {
        "previous", "prior", "above", "earlier",
        "instruction", "instructions",
        "guideline", "guidelines",
        "directive", "directives",
        "prompt", "prompts",
        "persona", "personality",
        "restriction", "restrictions", "constraint", "constraints",
    }
    REVEAL = {
        "reveal", "show", "print", "display", "repeat", "output",
        "expose", "dump", "leak", "describe", "explain",
    }
    ROLE_VERBS = {
        "act", "pretend", "behave", "roleplay", "imagine", "suppose",
        "become", "transform", "simulate",
    }
    ROLE_TARGETS = {
        "dan", "jailbreak", "jailbroken", "unrestricted", "unlocked",
        "free", "admin", "administrator", "root", "god", "evil",
        "unfiltered", "uncensored", "unchained",
    }
    EXPLICIT_JAILBREAK = {"jailbreak", "jailbroken", "dan"}

    # ---- L4: regex sentinels ---------------------------------------
    INJECTION_REGEX = [
        re.compile(r"\bsystem\s+(prompt|message|instruction|directive)s?\b"),
        re.compile(r"\byou\s+are\s+now\b"),
        re.compile(
            r"\bfrom\s+now\s+on\b.{0,40}\b(act|behave|pretend|respond|answer|reply)\b"
        ),
        re.compile(r"<\|(system|im_start|im_end|endoftext|im_sep)\|>"),
        re.compile(r"###\s*system\s*:"),
        re.compile(r"\[/?inst\]"),
        re.compile(
            r"\b(developer|dan|jailbreak|unrestricted|uncensored|unfiltered)\s+mode\b"
        ),
        re.compile(r"\bnew\s+(instructions?|rules?|prompt|system)\s*:"),
    ]

    # ---- L5: off-topic ---------------------------------------------
    OFF_TOPIC_KEYWORDS = [
        "weather", "forecast", "president", "politics", "election",
        "religion", "god", "joke", "recipe", "sing", "song",
        "who are you", "what is your name", "who made you",
        "who created you", "tell me a story",
    ]

    # ---- L6: global language block ---------------------------------
    BLOCKED_LANGUAGES = [
        "python", "javascript", "typescript", "rust", "java",
        "ruby", "golang", "go lang", "kotlin", "swift", "php",
        "perl", "scala", "haskell", "elixir", "clojure",
        "nodejs", "node.js",
    ]

    # ---- L8: plan-type blocked verbs -------------------------------
    PLAN_TYPE_BLOCKED_VERBS = [
        "write file", "write to file", "create file", "create a file",
        "save to", "save the file", "delete file", "delete the file",
        "edit the file", "edit this file", "modify the file",
        "modify this file", "patch the file", "apply this patch",
        "mkdir", "rmdir", "touch ",
        "run build", "run the build", "dotnet build", "g++ ", "clang++ ",
        "compile and run", "make install",
    ]

    # ================================================================
    # Public entry point
    # ================================================================
    @classmethod
    def check(
        cls,
        user_input: str,
        *,
        can_edit_files: bool,
        allowed_languages: tuple[str, ...] = ("cpp", "csharp"),
    ) -> GuardrailResult:
        text = (user_input or "").strip()
        if not text:
            return GuardrailResult(False, "Empty input.", "size")
        if len(text) > cls.MAX_INPUT_LEN:
            return GuardrailResult(
                False, f"🚫 Input exceeds {cls.MAX_INPUT_LEN} characters.", "size"
            )

        raw = text.lower()
        norm = cls._normalize(text)

        # L2: fuzzy injection — check both raw and normalized forms
        for form in (raw, norm):
            reason = cls._detect_injection(form)
            if reason:
                return GuardrailResult(
                    False,
                    f"🚫 GUARDRAIL: Prompt-injection detected ({reason}). "
                    "Submit a normal C++ or C# coding request.",
                    "injection_fuzzy",
                )

               # L3: encoding — decode and re-scan every decoded payload
        for payload in cls._detect_encoding(text):
            for form in (payload.lower(), cls._normalize(payload)):
                reason = cls._detect_injection(form, decoded=True)
                if reason:
                    return GuardrailResult(
                        False,
                        f"🚫 GUARDRAIL: Encoded prompt-injection detected ({reason}).",
                        "injection_encoded",
                    )

        # L4: regex sentinels
        for pat in cls.INJECTION_REGEX:
            if pat.search(raw) or pat.search(norm):
                return GuardrailResult(
                    False,
                    "🚫 GUARDRAIL: Prompt-injection pattern detected.",
                    "injection_regex",
                )

        # L5: off-topic (raw only — normalization strips useful context)
        for kw in cls.OFF_TOPIC_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", raw):
                return GuardrailResult(
                    False,
                    "🚫 GUARDRAIL: Off-topic query. "
                    "I only assist with C++ and C# development.",
                    "off_topic",
                )

        # L6: global language restriction
        for lang in cls.BLOCKED_LANGUAGES:
            if re.search(rf"\b{re.escape(lang)}\b", raw):
                return GuardrailResult(
                    False,
                    f"🚫 GUARDRAIL: Language restricted. I only write C++ and C# "
                    f"(blocked: {lang}).",
                    "language_global",
                )

        # L7: per-agent language scope
        mentioned_cpp = bool(CPP_PATTERN.search(raw))
        mentioned_cs = bool(CS_PATTERN.search(raw))
        if mentioned_cpp and "cpp" not in allowed_languages:
            return GuardrailResult(
                False,
                "🚫 GUARDRAIL: This agent only writes **C#** — you mentioned C++. "
                "Press F2 / Ctrl+T / Tab to switch to a C++ agent (Agent1 or Agent3).",
                "language_scope",
            )
        if mentioned_cs and "csharp" not in allowed_languages:
            return GuardrailResult(
                False,
                "🚫 GUARDRAIL: This agent only writes **C++** — you mentioned C#. "
                "Press F2 / Ctrl+T / Tab to switch to a C# agent (Agent2 or Agent4).",
                "language_scope",
            )

        # L8: plan-type edit block
        if not can_edit_files:
            for verb in cls.PLAN_TYPE_BLOCKED_VERBS:
                if verb in raw:
                    return GuardrailResult(
                        False,
                        "🚫 GUARDRAIL: This is a plan-type agent — it may not "
                        "edit files or run builds. Press F2 / Ctrl+T / Tab to "
                        "switch to a build-type agent (Agent2, Agent4, or Agent5).",
                        "plan_type",
                    )

        return GuardrailResult(True)

    # ================================================================
    # L1 — normalization
    # ================================================================
    @classmethod
    def _normalize(cls, text: str) -> str:
        # 1. Unicode NFKD — decomposes accented chars, ligatures
        text = unicodedata.normalize("NFKD", text)
        # 2. Transliterate common homoglyphs (Cyrillic о → Latin o, etc.)
        text = text.translate(cls.HOMOGLYPHS)
        # 3. Drop remaining non-ASCII (the "ignore" defence)
        text = text.encode("ascii", errors="ignore").decode("ascii")
        # 4. Lowercase
        text = text.lower()
        # 5. Strip control characters and zero-width spaces
        text = "".join(ch for ch in text if ch.isprintable() or ch in " \t\n")
        # 6. De-leet (1→i, 0→o, 3→e, ...)
        text = text.translate(cls.LEET_MAP)
        # 7. Collapse whitespace
        return re.sub(r"\s+", " ", text).strip()

    # ================================================================
    # L2 — fuzzy injection detection
    # ================================================================
    @staticmethod
    def _edit_distance_leq(a: str, b: str, max_dist: int) -> bool:
        """Bounded Levenshtein distance — early-exits when exceeded."""
        if a == b:
            return True
        la, lb = len(a), len(b)
        if abs(la - lb) > max_dist:
            return False
        if la == 0 or lb == 0:
            return max(la, lb) <= max_dist
        prev = list(range(lb + 1))
        for i in range(1, la + 1):
            curr = [i] + [0] * lb
            row_min = curr[0]
            for j in range(1, lb + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
                if curr[j] < row_min:
                    row_min = curr[j]
            if row_min > max_dist:
                return False
            prev = curr
        return prev[lb] <= max_dist

    @classmethod
    def _fuzzy_match(cls, token: str, wordset: set[str]) -> bool:
        # Exact match always counts.
        if token in wordset:
            return True
        # Short tokens are too easy to false-match (e.g. "a" → "act", "dan").
        if len(token) < cls.MIN_FUZZY_LEN:
            return False
        for kw in wordset:
            if len(kw) < cls.MIN_FUZZY_LEN:
                continue
            # Tiered tolerance: only long-vs-long allows distance 2.
            max_d = (
                cls.MAX_TOKEN_DIST_LONG
                if (len(token) >= 6 and len(kw) >= 6)
                else cls.MAX_TOKEN_DIST_SHORT
            )
            if cls._edit_distance_leq(token, kw, max_d):
                return True
        return False
    @classmethod
    def _detect_injection(cls, text: str, *, decoded: bool = False) -> str | None:
        tokens = re.findall(r"[a-z]+", text.lower())
        if not tokens:
            return None

        verb_idx = [i for i, t in enumerate(tokens) if cls._fuzzy_match(t, cls.VERBS)]
        target_idx = [i for i, t in enumerate(tokens) if cls._fuzzy_match(t, cls.TARGETS)]
        reveal_idx = [i for i, t in enumerate(tokens) if cls._fuzzy_match(t, cls.REVEAL)]
        rv_idx = [i for i, t in enumerate(tokens) if cls._fuzzy_match(t, cls.ROLE_VERBS)]
        rt_idx = [i for i, t in enumerate(tokens) if cls._fuzzy_match(t, cls.ROLE_TARGETS)]
        jail_idx = [i for i, t in enumerate(tokens) if cls._fuzzy_match(t, cls.EXPLICIT_JAILBREAK)]

        def near(a: list[int], b: list[int], window: int = 10) -> bool:
            return any(abs(i - j) <= window for i in a for j in b)

        if verb_idx and target_idx and near(verb_idx, target_idx):
            return "instruction override"
        if reveal_idx and target_idx and near(reveal_idx, target_idx):
            return "prompt extraction"
        if rv_idx and rt_idx and near(rv_idx, rt_idx):
            return "role change"
        if jail_idx:
            return "explicit jailbreak term"

        # Concatenation fallback — catches encoded payloads like
        # "ignoreprevious" after base64 decoding
        # Concatenation fallback — ONLY safe on decoded payloads where
        # spaces may have been stripped (e.g. hex-escaped "ignoreprevious").
        # On raw user text it causes false positives ("ignore prior" → "ignoreprior").
        if decoded:
            flat = "".join(tokens)
            for v in cls.VERBS:
                for t in cls.TARGETS:
                    if (v + t) in flat or (t + v) in flat:
                        return "instruction override (concatenated)"

        return None

    # ================================================================
    # L3 — encoding detection
    # ================================================================
    @classmethod
    def _detect_encoding(cls, text: str) -> list[str]:
        """Return every decoded candidate payload we can extract."""
        out: list[str] = []

        # Base64 — require ≥20 chars to avoid false positives on normal text
        for m in re.finditer(r"\b[A-Za-z0-9+/]{20,}={0,2}", text):
            try:
                decoded = base64.b64decode(m.group(), validate=True).decode(
                    "utf-8", errors="ignore"
                )
                if decoded and (decoded.isprintable() or "\n" in decoded):
                    out.append(decoded)
            except Exception:
                pass

        # Hex escapes — \x41\x42... (min 4)
        hex_bytes = re.findall(r"\\x[0-9a-fA-F]{2}", text)
        if len(hex_bytes) >= 4:
            try:
                out.append(
                    bytes(int(h[2:], 16) for h in hex_bytes).decode(
                        "utf-8", errors="ignore"
                    )
                )
            except Exception:
                pass

        # URL encoding — %41%42... (min 4)
        if len(re.findall(r"%[0-9a-fA-F]{2}", text)) >= 4:
            try:
                out.append(urllib.parse.unquote(text))
            except Exception:
                pass

        # ROT13 — only if the user explicitly mentions it
        if "rot13" in text.lower():
            try:
                out.append(codecs.decode(text, "rot_13"))
            except Exception:
                pass

        return out