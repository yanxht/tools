"""Voice map, locale detection, and voice resolution for the Azure backend."""
import langid

VOICE_MAP = {
    "en-US": {"Female": "en-US-AvaMultilingualNeural", "Male": "en-US-AndrewMultilingualNeural"},
    "en-GB": {"Female": "en-GB-SoniaNeural", "Male": "en-GB-RyanNeural"},
    "zh-CN": {"Female": "zh-CN-XiaoxiaoMultilingualNeural", "Male": "zh-CN-YunyiMultilingualNeural"},
    "zh-TW": {"Female": "zh-TW-HsiaoChenNeural", "Male": "zh-TW-YunJheNeural"},
    "ja-JP": {"Female": "ja-JP-NanamiNeural", "Male": "ja-JP-KeitaNeural"},
    "ko-KR": {"Female": "ko-KR-SunHiNeural", "Male": "ko-KR-InJoonNeural"},
    "es-ES": {"Female": "es-ES-ElviraNeural", "Male": "es-ES-AlvaroNeural"},
    "fr-FR": {"Female": "fr-FR-DeniseNeural", "Male": "fr-FR-HenriNeural"},
    "de-DE": {"Female": "de-DE-KatjaNeural", "Male": "de-DE-ConradNeural"},
}

LANGID_TO_LOCALE = {
    "en": "en-US", "zh": "zh-CN", "ja": "ja-JP", "ko": "ko-KR",
    "es": "es-ES", "fr": "fr-FR", "de": "de-DE",
}

LOCALE_NAMES = {
    "en-US": "English (US)", "en-GB": "English (UK)", "zh-CN": "Chinese (Mandarin)",
    "zh-TW": "Chinese (Taiwanese)", "ja-JP": "Japanese", "ko-KR": "Korean",
    "es-ES": "Spanish", "fr-FR": "French", "de-DE": "German",
}


def detect_locale(text: str) -> str:
    lang, _ = langid.classify(text)
    return LANGID_TO_LOCALE.get(lang, "en-US")


def resolve_voice(locale: str, gender: str = "Female") -> str:
    """Resolve a voice name from locale + gender, with graceful fallback."""
    if locale in VOICE_MAP:
        return VOICE_MAP[locale].get(gender, VOICE_MAP[locale]["Female"])
    prefix = locale.split("-")[0]
    for key in VOICE_MAP:
        if key.startswith(prefix + "-"):
            return VOICE_MAP[key].get(gender, VOICE_MAP[key]["Female"])
    return VOICE_MAP["en-US"].get(gender, VOICE_MAP["en-US"]["Female"])


def print_voice_table():
    print(f"\n{'Language':<22} {'Locale':<10} {'Female Voice':<40} {'Male Voice'}")
    print("-" * 110)
    for locale, voices in VOICE_MAP.items():
        name = LOCALE_NAMES.get(locale, locale)
        print(f"{name:<22} {locale:<10} {voices['Female']:<40} {voices['Male']}")
    print()
