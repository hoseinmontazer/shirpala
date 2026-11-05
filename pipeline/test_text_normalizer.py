"""Regression checks for Persian TTS pronunciation normalization."""

from pipeline.text_normalizer import normalize_mixed_persian_english_text


def _n(text: str) -> str:
    return normalize_mixed_persian_english_text(text, enable_auto_learning=False)


def test_podcast_and_server_vocalization():
    out = _n("این پادکست درباره سرورها و پادکست‌ها است")
    assert "پادکاست" in out
    assert "پادکست" not in out.replace("پادکاست", "")
    assert "سِروِر" in out


def test_node_morphology_and_ninety_protection():
    out = _n("نودهایی که خراب شدند و p99 برابر نود درصد بود و نود و نه میلی‌ثانیه")
    assert "گره‌هایی" in out or "گره\u200cهایی" in out
    assert "پی نود و نه" in out
    assert "نود درصد" in out
    assert "نود و نه" in out
    assert "پی گره" not in out
    assert "گره درصد" not in out


def test_version_spacing_not_glued():
    out = _n("محدودیت‌های v1 و از v1.35 کوبرنتیز")
    assert "هایورژن" not in out
    assert "ازنسخه" not in out
    assert "1. 35" not in out
    assert "ممیز" in out
    # Digits should be spoken as Persian words for Piper
    assert "یک" in out
    assert "سی و پنج" in out or "سی‌و‌پنج" in out or "سی و پنج" in out


def test_bare_persian_version_decimal_not_split():
    out = _n("پیش از نسخه 1.35 کوبرنتیز")
    assert "1. 35" not in out
    assert "ممیز" in out


def test_digits_spoken_for_piper():
    out = _n("با 99 درصد و 12 پاد")
    assert "نود و نه" in out
    assert "دوازده" in out
    assert "99" not in out


def test_cluster_spellings_and_devops():
    out = _n("کلستر و کلاستر و DevOps و دوآپس")
    assert "کِلاستِر" in out
    assert "دِواپس" in out
    assert "کلستر" not in out.replace("کِلاستِر", "")


def test_brand_not_nawli():
    out = _n("به Knowly خوش آمدید در blog.knowly.ir")
    assert "نولی" in out
    assert "ناولی" not in out
    assert "بلاگ نولی" in out
    assert "blog.knowly" not in out.lower()


def test_kubernetes_terms():
    out = _n("Kubelet on the Node runs the Pod in the Cluster")
    assert "کیوب‌لِت" in out
    assert "گره" in out
    assert "پاد" in out
    assert "کِلاستِر" in out


def test_english_parentheticals_stripped():
    import re
    out = _n("ایزوله‌سازی (Isolation) و حافظه (Memory) در cgroup v2")
    assert "Isolation" not in out
    assert "Memory" not in out
    assert not re.search(r"[A-Za-z]", out)
    assert "سی‌گروپ" in out


def test_no_latin_left_for_piper():
    out = _n(
        "برای مهندسان SRE و DevOps، kubelet روی Node با Pod و Deployment "
        "و StatefulSet در Kubernetes مهم است. همچنین File Capabilities و User Namespaces."
    )
    assert not re.search(r"[A-Za-z]", out), out
    assert "اس‌آر‌ای" in out or "اس‌آر" in out
    assert "دِواپس" in out
    assert "کیوب‌لِت" in out


if __name__ == "__main__":
    import re

    test_podcast_and_server_vocalization()
    test_node_morphology_and_ninety_protection()
    test_version_spacing_not_glued()
    test_bare_persian_version_decimal_not_split()
    test_digits_spoken_for_piper()
    test_cluster_spellings_and_devops()
    test_brand_not_nawli()
    test_kubernetes_terms()
    test_english_parentheticals_stripped()
    test_no_latin_left_for_piper()
    print("All text_normalizer pronunciation regressions passed.")
