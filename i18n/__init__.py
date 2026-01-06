DEFAULT_LANG = "ru"

def pick_lang(lang: str | None, mapping: dict[str, str]) -> str:
    if not isinstance(lang, str) or not lang:
        lang = DEFAULT_LANG
    if lang in mapping:
        return mapping[lang]
    if "en" in mapping:
        return mapping["en"]
    if DEFAULT_LANG in mapping:
        return mapping[DEFAULT_LANG]
    return next(iter(mapping.values()))
