"""
Devanagari to Hinglish (Romanized Hindi) Transliteration Engine
Pure Python implementation with colloquial phonetic rules for viral short-form video subtitles.
"""

import re
from typing import Dict

# Direct dictionary for common Hindi words for 100% natural colloquial Hinglish
COMMON_HINGLISH_DICT: Dict[str, str] = {
    "है": "hai", "हैं": "hain", "हो": "ho", "था": "tha", "थी": "thi", "थे": "the",
    "में": "mein", "से": "se", "को": "ko", "का": "ka", "की": "ki", "के": "ke",
    "ने": "ne", "पर": "par", "पे": "pe", "भी": "bhi", "तो": "toh", "ना": "na",
    "नहीं": "nahi", "नही": "nahi", "मत": "mat", "क्या": "kya", "क्यों": "kyun",
    "कहाँ": "kahan", "कहा": "kaha", "यहाँ": "yahan", "यहा": "yahan", "वहाँ": "wahan",
    "वहा": "wahan", "कैसे": "kaise", "कब": "kab", "कौन": "kaun", "किस": "kis",
    "भाई": "bhai", "यार": "yaar", "दोस्त": "dost", "गाड़ी": "gaadi", "गाड़ी": "gaadi",
    "बात": "baat", "काम": "kaam", "नाम": "naam", "लोग": "log", "घर": "ghar",
    "अच्छा": "achha", "अच्छी": "achhi", "अच्छे": "achhe", "बहुत": "bahut",
    "ज्यादा": "zyada", "कम": "kam", "बड़ा": "bada", "छोटा": "chhota",
    "सुनो": "suno", "देखो": "dekho", "करो": "karo", "बोलो": "bolo",
    "चलो": "chalo", "जाओ": "jao", "आओ": "aao", "भागो": "bhaago", "भागाओ": "bhaagao",
    "गया": "gaya", "गई": "gayi", "गए": "gaye", "रहा": "raha", "रही": "rahi", "रहे": "rahe",
    "मिला": "mila", "मिली": "mili", "मिले": "mile", "लिया": "liya", "ली": "lee", "दिए": "diye",
    "खत्म": "khatam", "खतम": "khatam", "वाट": "vaat", "मजा": "maza", "मज़ा": "maza",
    "खजाना": "khazana", "पैसा": "paisa", "पैसे": "paise", "रुपया": "rupya", "रुपये": "rupaye",
    "लाल": "laal", "मैप": "map", "गाड़ी": "gaadi", "पुलिस": "police", "कार": "car",
    "ढूंढने": "dhoondhne", "ढूंढो": "dhoondho", "सिग्नल": "signal", "ड्राइविंग": "driving",
    "खतरनाक": "khatarnaak", "लौंडे": "launde", "साले": "saale", "अरे": "arre", "ओ": "o",
    "अभी": "abhi", "आएगा": "aayega", "आएगी": "aayegi", "आएंगे": "aayenge", "करवाने": "karwane",
    "लिए": "liye", "इसको": "isko", "उसको": "usko", "इस": "is", "उस": "us", "सब": "sab",
    "कुछ": "kuchh", "कोई": "koi", "एक": "ek", "दो": "do", "तीन": "teen", "चार": "char",
    "होगा": "hoga", "होगी": "hogi", "होंगे": "honge", "करना": "karna", "करने": "karne",
    "हुआ": "hua", "हुई": "hui", "हुए": "hue", "हीट": "heat", "गेम": "game", "गाड़ी": "gaadi",
    "ध्यान": "dhyan", "बोल": "bol", "सुन": "sun", "रहेंगे": "rahenge", "रहेगा": "rahega",
    "रह": "rah", "जा": "ja", "रहा": "raha", "रही": "rahi", "गए": "gaye"
}

# Devanagari Unicode components
VOWELS = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ऋ': 'ri', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au',
}

MATRAS = {
    'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
    'ृ': 'ri', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au',
}

CONSONANTS = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'f', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v',
    'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'क्ष': 'ksh', 'त्र': 'tr', 'ज्ञ': 'gy',
    'ड़': 'r', 'ढ़': 'rh', 'ज़': 'z', 'फ़': 'f', 'क़': 'q', 'ख़': 'kh', 'ग़': 'gh'
}

HALANT = '्'
ANUSVARA = 'ं'
CHANDRABINDU = 'ँ'
VISARGA = 'ः'
NUKTA = '़'


def is_devanagari(text: str) -> bool:
    """Checks if text contains Devanagari characters."""
    return any('\u0900' <= char <= '\u097F' for char in text)


def transliterate_word(word: str) -> str:
    """Transliterates a single Devanagari word into natural colloquial Hinglish."""
    clean_w = word.strip().replace("।", "").replace("॥", "")
    if not clean_w or not is_devanagari(clean_w):
        return clean_w

    # Strip punctuation for lookup
    punct_prefix = ""
    punct_suffix = ""
    while clean_w and clean_w[0] in ".,!?:;\"'()[]{}<>-":
        punct_prefix += clean_w[0]
        clean_w = clean_w[1:]
    while clean_w and clean_w[-1] in ".,!?:;\"'()[]{}<>-|।":
        punct_suffix += clean_w[-1]
        clean_w = clean_w[:-1]

    # Check direct dictionary lookup first
    if clean_w in COMMON_HINGLISH_DICT:
        res = COMMON_HINGLISH_DICT[clean_w]
        return punct_prefix + res + punct_suffix

    # Phonetic transliteration algorithm
    out = []
    i = 0
    n = len(clean_w)

    while i < n:
        char = clean_w[i]

        # Handle nukta combinations (e.g. ड़, ज़, फ़)
        if i + 1 < n and clean_w[i + 1] == NUKTA:
            combo = char + NUKTA
            if combo in CONSONANTS:
                out.append(CONSONANTS[combo])
                # Check next for matra or halant
                i += 2
                if i < n:
                    next_char = clean_w[i]
                    if next_char in MATRAS:
                        out.append(MATRAS[next_char])
                        i += 1
                    elif next_char == HALANT:
                        i += 1
                    elif next_char in (ANUSVARA, CHANDRABINDU):
                        out.append('n')
                        i += 1
                    else:
                        if i < n and (clean_w[i] in CONSONANTS or clean_w[i] in VOWELS):
                            out.append('a')
                continue

        if char in VOWELS:
            out.append(VOWELS[char])
            i += 1
        elif char in CONSONANTS:
            base_cons = CONSONANTS[char]
            out.append(base_cons)
            i += 1
            if i < n:
                next_char = clean_w[i]
                if next_char in MATRAS:
                    out.append(MATRAS[next_char])
                    i += 1
                elif next_char == HALANT:
                    i += 1 # Suppresses inherent 'a'
                elif next_char in (ANUSVARA, CHANDRABINDU):
                    out.append('an')
                    i += 1
                else:
                    # Inherent 'a' if not at the end of word (schwa deletion rule)
                    if i < n and clean_w[i] in CONSONANTS:
                        # Don't add 'a' if following letter is at end or common cluster
                        out.append('a')
        elif char in MATRAS:
            out.append(MATRAS[char])
            i += 1
        elif char in (ANUSVARA, CHANDRABINDU):
            out.append('n')
            i += 1
        elif char == VISARGA:
            out.append('h')
            i += 1
        elif char == '।':
            out.append('.')
            i += 1
        else:
            out.append(char)
            i += 1

    roman = "".join(out)
    return punct_prefix + roman + punct_suffix


def to_hinglish(text: str) -> str:
    """Converts a full sentence or phrase from Devanagari to natural Hinglish."""
    if not is_devanagari(text):
        return text

    words = text.split(" ")
    transliterated = [transliterate_word(w) for w in words]
    return " ".join(transliterated)


if __name__ == "__main__":
    test_cases = [
        "सुनो ध्यान से... हो गया, भागो भागाओ! वाट लग गई भागो यहां से!",
        "भाई हीट खत्म? अच्छा अभी खत्म हुआ है... ओ लाल है अभी भी मैप!",
        "भाई इसको ढूंढने में बहुत मज़ा आएगा... चलो मिला कुछ!",
        "$2000 लिया है भाई ड्राइविंग करवाने के लिए!"
    ]
    for tc in test_cases:
        print("HINDI:   ", tc)
        print("HINGLISH:", to_hinglish(tc))
        print("-" * 50)
