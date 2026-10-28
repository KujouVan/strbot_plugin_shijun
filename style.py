"""Legacy compatibility helpers. AstrBot owns the active persona prompt."""
OPEN_MARKER = '<natural_style_supplement_v1>'
CLOSE_MARKER = '</natural_style_supplement_v1>'
DEFAULT_STYLE = ''


def supplement_system_prompt(original: str, custom_style: str = '') -> str:
    return original
