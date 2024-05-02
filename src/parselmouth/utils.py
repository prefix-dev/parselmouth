import re


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()
