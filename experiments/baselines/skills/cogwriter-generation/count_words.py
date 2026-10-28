"""Print the CogWriter word count of a file.

The counting follows ``count_words`` in CogWriter's ``utils/wordCounter.py``
(KaiyangWan/CogWriter@dc3bf084e8733c951172cddd89fa4d7337121fdd): each CJK
Unified Ideograph counts as one word, and the rest counts whitespace-separated
runs after punctuation other than ``^``, ``-``, ``.``, and ``'`` becomes space.
"""

import re
import sys
from pathlib import Path


def count_words(text: str) -> int:
    """Return CogWriter's word count of ``text``."""

    text = text.replace("　", " ")
    chinese_count = len(re.findall(r"[一-鿿]", text))
    english_text = re.sub(r"[一-鿿]", " ", text)
    english_text = re.sub(r"[^\w\s\^\-\.\']", " ", english_text)
    return chinese_count + len(english_text.split())


if __name__ == "__main__":
    print(count_words(Path(sys.argv[1]).read_text(encoding="utf-8")))
