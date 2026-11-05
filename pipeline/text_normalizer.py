import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from .config import PIPELINE_DATA_DIR, NEXUSLLM_API_KEY, NEXUSLLM_BASE_URL, NEXUSLLM_MODEL

# Persistent auto-learning cache (honors PIPELINE_DATA_DIR for Docker /app/data)
CACHE_DIR = PIPELINE_DATA_DIR
CACHE_FILE = CACHE_DIR / "phonetic_cache.json"

# Phonetic Persian sounds for English alphabet letters
LETTER_SOUNDS: Dict[str, str] = {
    "A": "ای", "B": "بی", "C": "سی", "D": "دی", "E": "ای", "F": "اف",
    "G": "جی", "H": "اچ", "I": "آی", "J": "جی", "K": "کی", "L": "ال",
    "M": "ام", "N": "ان", "O": "او", "P": "پی", "Q": "کیو", "R": "آر",
    "S": "اس", "T": "تی", "U": "یو", "V": "وی", "W": "دبلیو", "X": "ایکس",
    "Y": "وای", "Z": "زد"
}

# Core Seed Technical Dictionary: English -> Persian Phonetic
BASE_TECHNICAL_DICTIONARY: Dict[str, str] = {
    # Organizations & Communities
    "Kubernetes": "کوبرنتیز",
    "k8s": "کوبرنتیز",
    "CNCF": "سی‌ان‌سی‌اف",
    "Cloud Native": "کلود نیتیو",
    "Cloudflare": "کلودفلر",
    "Grafana Labs": "گرافانا لبز",
    "Grafana": "گرافانا",
    "Prometheus": "پرومتئوس",
    "OpenTelemetry": "اوپن‌تله‌متری",
    "Linux Foundation": "بنیاد لینوکس",

    # Brand
    "Knowly": "نولی",
    "knowly": "نولی",

    # Core Roles & Practices
    # Vocalized form: plain «دوآپس/دواپس» is often misread by TTS engines.
    "DevOps": "دِواپس",
    "SREs": "مهندسان اس‌آر‌ای",
    "SRE": "اس‌آر‌ای",
    "Site Reliability Engineering": "مهندسی قابلیت اطمینان سایت",
    "CI/CD": "سی‌آی‌سی‌دی",
    "GitOps": "گیت‌اپس",
    "FinOps": "فین‌اپس",
    "SysAdmin": "سیس‌ادمین",
    "Bare-metal": "بِیرمِتل",
    "Bare Metal": "بِیرمِتل",
    "bare-metal": "بِیرمِتل",

    # Architecture & Patterns
    "Microservices": "میکروسرویس‌ها",
    "Microservice": "میکروسرویس",
    "Monolith": "مونولیت",
    "Distributed Systems": "سیستم‌های توزیع‌شده",
    "High Availability": "دسترسی‌پذیری بالا",
    "HA": "اچ‌ای",
    "Failover": "فیل‌اور",
    "Zero-downtime": "زیرو داون‌تایم",
    "Rolling Update": "رولینگ آپدیت",
    "Canary": "کاناری",
    "Blue-Green": "بلو گرین",
    "Service Mesh": "سرویس مش",
    "Sidecar": "سایدکار",
    "Self-healing": "خودترمیمی",
    "Rootless": "روت‌لس",
    "Multi-tenant": "چندمستاجره",
    "Sandbox": "سندباکس",
    "Agentic": "ایجنتیک",
    "Agent": "ایجنت",
    "AI": "هوش مصنوعی",
    "LLM": "ال‌ال‌ام",
    "LLMs": "ال‌ال‌ام‌ها",
    "Machine Learning": "یادگیری ماشین",
    "ML": "ام‌ال",

    # Kubernetes Objects & Controllers
    "Deployments": "دیپلوی‌منت‌ها",
    "Deployment": "دیپلوی‌منت",
    "StatefulSets": "استیت‌فول‌ست‌ها",
    "StatefulSet": "استیت‌فول‌ست",
    "DaemonSets": "دیمن‌ست‌ها",
    "DaemonSet": "دیمن‌ست",
    "ReplicaSets": "رپلیکا‌ست‌ها",
    "ReplicaSet": "رپلیکا‌ست",
    "JobSets": "جاب‌ست‌ها",
    "JobSet": "جاب‌ست",
    "CronJobs": "کران‌جاب‌ها",
    "CronJob": "کران‌جاب",
    "Jobs": "جاب‌ها",
    "Job": "جاب",
    "Pods": "پادها",
    "Pod": "پاد",
    "Nodes": "نودها",
    "Node": "نود",
    "Clusters": "کلاسترها",
    "Cluster": "کلاستر",
    "Namespaces": "نیم‌اسپیس‌ها",
    "Namespace": "نیم‌اسپیس",
    "ConfigMaps": "کانفیگ‌مپ‌ها",
    "ConfigMap": "کانفیگ‌مپ",
    "Secrets": "سیکرت‌ها",
    "Secret": "سیکرت",
    "Ingress Controller": "اینگرس کنترلر",
    "Ingress": "اینگرس",
    "Egress": "ایگرس",
    "Services": "سرویس‌ها",
    "Service": "سرویس",
    "CRDs": "سی‌آردی‌ها",
    "CRD": "سی‌آردی",
    "Custom Resource Definition": "تعریف منبع سفارشی",
    "Kubelet": "کیوب‌لِت",
    "Kubeadm": "کیوب‌اَدمین",
    "Kubectl": "کیوب‌سی‌تی‌ال",
    "etcd": "ای‌تی‌سی‌دی",
    "CoreDNS": "کور دی‌ان‌اس",
    "SIG Apps": "سیگ اپس",
    "SIG Node": "سیگ نود",
    "SIG": "سیگ",
    "Node Lifecycle": "چرخه حیات نود",
    "Workload": "بار کاری",
    "Workloads": "بارهای کاری",

    # Linux & OS Internals
    "Linux": "لینوکس",
    "Kernel": "کرنل",
    "cgroup v2": "سی‌گروپ دو",
    "cgroup v1": "سی‌گروپ یک",
    "cgroups": "سی‌گروپ‌ها",
    "cgroup": "سی‌گروپ",
    "systemd": "سیستم‌دی",
    "eBPF": "ای‌بی‌پی‌اف",
    "BPF": "بی‌پی‌اف",
    "XDP": "ایکس‌دی‌پی",
    "VFS": "وی‌اف‌اس",
    "sysfs": "سیس‌اف‌اس",
    "procfs": "پراک‌اف‌اس",
    "User Namespaces": "یوزر نیم‌اسپیس‌ها",
    "User Namespace": "یوزر نیم‌اسپیس",
    "File Capabilities": "قابلیت‌های فایل",
    "Capabilities": "قابلیت‌ها",
    "Capability": "قابلیت",
    "OOM Killer": "او‌او‌ام کیلر",
    "OOM": "او‌او‌ام",
    "Out of Memory": "کمبود حافظه",
    "Memory QoS": "کیفیت خدمات حافظه",
    "QoS": "کیو‌او‌اس",
    "CPU": "سی‌پی‌یو",
    "RAM": "رم",
    "GPU": "جی‌پی‌یو",
    "TPU": "تی‌پی‌یو",
    "I/O": "آی‌او",
    "IOPS": "آی‌او‌پی‌اس",
    "SSD": "اس‌اس‌دی",
    "HDD": "هارد دیسک",
    "OS": "سیستم‌عامل",
    "xattrs": "اکستندد اتریبیوت‌ها",
    "Syscall": "سیستم کال",
    "Syscalls": "سیستم کال‌ها",

    # Networking & Protocols
    "IP Address Management": "مدیریت آدرس‌های آی‌پی",
    "IPAM": "آی‌پی‌ام",
    "IP Addresses": "آدرس‌های آی‌پی",
    "IP Address": "آدرس آی‌پی",
    "IP": "آی‌پی",
    "CIDR": "سایدر",
    "DNS": "دی‌ان‌اس",
    "TLS 1.3": "تی‌ال‌اس یک ممیز سه",
    "TLS": "تی‌ال‌اس",
    "SSL": "اس‌اس‌ال",
    "HTTP/2": "اچ‌تی‌تی‌پی دو",
    "HTTP/3": "اچ‌تی‌تی‌پی سه",
    "HTTPS": "اچ‌تی‌تی‌پی‌اس",
    "HTTP": "اچ‌تی‌تی‌پی",
    "TCP": "تی‌سی‌پی",
    "UDP": "یو‌دی‌پی",
    "BGP": "بی‌جی‌پی",
    "VPC": "وی‌پی‌سی",
    "NAT": "نت",
    "VPN": "وی‌پی‌ان",
    "WireGuard": "وایرگارد",
    "OpenSSL": "اوپن‌اس‌اس‌ال",
    "Cilium": "سیلیوم",
    "Calico": "کالیکو",
    "Envoy": "انوی",
    "Istio": "ایستیو",
    "Linkerd": "لینکردی",
    "Traefik": "ترافیک",
    "Nginx": "انجین‌ایکس",
    "HAProxy": "اچ‌ای‌پراکسی",

    # Observability & Monitoring
    "Observability": "مشاهده‌پذیری",
    "Telemetry": "تله‌متری",
    "Metrics": "متریک‌ها",
    "Metric": "متریک",
    "Logs": "لاگ‌ها",
    "Log": "لاگ",
    "Logging": "ثبت لاگ",
    "Tracing": "ردیابی",
    "Traces": "تریس‌ها",
    "Alerting": "هشداردهی",
    "Alerts": "هشدارها",
    "Loki": "لوکی",
    "Tempo": "تمپو",
    "Jaeger": "یگر",
    "Thanos": "تانوس",
    "Datadog": "دیتاداگ",

    # Databases & Storage
    "PostgreSQL": "پستگرس‌کیو‌ال",
    "Postgres": "پستگرس",
    "MySQL": "مای‌اس‌کیو‌ال",
    "SQLite": "اس‌کیولایت",
    "Redis": "ردیس",
    "Kafka": "کافکا",
    "RabbitMQ": "ربیت‌ام‌کیو",
    "NATS": "نتس",
    "Elasticsearch": "الاستیک‌سرچ",
    "OpenSearch": "اوپن‌سرچ",
    "SQL": "اس‌کیو‌ال",
    "NoSQL": "نو‌اس‌کیو‌ال",
    "DB": "دیتابیس",

    # Containers & Tools
    "Docker": "داکر",
    "Podman": "پادمن",
    "Containerd": "کانتینردی",
    "CRI-O": "سی‌آر‌آی‌او",
    "Helm": "هلم",
    "Kustomize": "کاستومایز",
    "ArgoCD": "آرگوسی‌دی",
    "Terraform": "ترافورم",
    "Ansible": "انسیبل",
    "GitHub": "گیت‌هاب",
    "GitLab": "گیت‌لب",
    "Git": "گیت",

    # Formats & Standards
    "YAML": "یمل",
    "JSON": "جیسون",
    "XML": "ایکس‌ام‌ال",
    "REST API": "رست ای‌پی‌آی",
    "REST": "رست",
    "gRPC": "جی‌آر‌پی‌سی",
    "API": "ای‌پی‌آی",
    "CLI": "سی‌ال‌آی",
    "UI": "یو‌آی",
    "UX": "یو‌ایکس",
    "CVE": "سی‌وی‌ای",
    "PR": "پی‌آر",
    "Pull Request": "پول ریکوئست",
    "Issue": "ایشو",

    # Media & Platforms
    "podcast": "پادکاست",
    "podcasts": "پادکاست‌ها",
    "blog": "بلاگ",
    "post": "پست",

    # Cloud Providers
    "AWS": "ای‌دبلیواس",
    "GCP": "جی‌سی‌پی",
    "Azure": "آژور",

    # Languages
    "Golang": "زبان گو",
    "Go": "گو",
    "Rust": "راست",
    "Python": "پایتون",
    "Bash": "بش",

    # Frequent English leftovers inside FA article bodies / parentheses
    # Prefer spoken Persian meaning when clear; else phonetic form for Piper.
    "cgroup": "سی‌گروپ",
    "Cgroup": "سی‌گروپ",
    "CGroup": "سی‌گروپ",
    "kubelet": "کیوب‌لِت",
    "kubectl": "کیوب‌سی‌تی‌ال",
    "kubeadm": "کیوب‌اَدمین",
    "Memory": "حافظه",
    "memory": "حافظه",
    "User": "کاربر",
    "File": "فایل",
    "Files": "فایل‌ها",
    "Capabilities": "قابلیت‌ها",
    "Capability": "قابلیت",
    "Lifecycle": "چرخه حیات",
    "Lifecycles": "چرخه‌های حیات",
    "Resilience": "تاب‌آوری",
    "Batch": "بَچ",
    "Request": "ریکئوست",
    "Requests": "ریکئوست‌ها",
    "Limit": "لیمیت",
    "Limits": "لیمیت‌ها",
    "Root": "روت",
    "Hard": "هارد",
    "Soft": "سافت",
    "Stateless": "بدون حالت",
    "Stateful": "با حالت",
    "Isolation": "ایزوله‌سازی",
    "Hierarchy": "سلسله‌مراتب",
    "Unified": "یکپارچه",
    "Maintenance": "نگهداری",
    "Production": "پروداکشن",
    "Warning": "هشدار",
    "Error": "خطا",
    "Guaranteed": "گَرَنتید",
    "Burstable": "بِرستِبِل",
    "BestEffort": "بِست اِفِرت",
    "Ordering": "ترتیب",
    "Serving": "سروینگ",
    "Working Group": "گروه کاری",
    "Workload Lifecycles": "چرخه حیات بار کاری",
    "Update Strategy": "استراتژی آپدیت",
    "Rollout": "رول‌آوت",
    "Evict": "اِویکت",
    "Eviction": "اخراج پاد",
    "Overcommitting": "اُورکِمیت",
    "Overcommit": "اُورکِمیت",
    "TieredReservation": "رزرو لایه‌ای",
    "singleProcessOOMKill": "سینگل پراسس او‌او‌ام کیل",
    "failCgroupV1": "فیل سی‌گروپ یک",
    "SystemVerification": "سیستم وریفیکیشن",
    "init": "اِینیت",
    "join": "جُوین",
    "upgrade": "آپگرید",
    "active_file": "اکتیو فایل",
    "memory.oom.group": "مموری او‌او‌ام گروپ",
    "memory.events": "مموری ایونتس",
    "ipam": "آی‌پی‌ام",
    "IPAM": "آی‌پی‌ام",
    "LXC": "ال‌ایکس‌سی",
    "VFS": "وی‌اف‌اس",
    "Wider System": "سیستم وسیع‌تر",
    "Parent": "والد",
    "Mode": "حالت",
}

# Runtime Dynamic Cache (Auto-Learning)
DYNAMIC_CACHE: Dict[str, str] = {}

def _load_persistent_cache():
    """Load previously learned transliterations from disk."""
    global DYNAMIC_CACHE
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                DYNAMIC_CACHE = json.load(f)
        except Exception:
            DYNAMIC_CACHE = {}

def _save_persistent_cache():
    """Save newly learned transliterations to disk for future runs."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(DYNAMIC_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TextNormalizer] Cache save warning: {e}")

# Load cache on module import
_load_persistent_cache()

# Brand / quality overrides that must always win over a polluted auto-learn cache.
_DICTIONARY_OVERRIDES: Dict[str, str] = {
    "Knowly": "نولی",
    "knowly": "نولی",
    "DevOps": "دِواپس",
    "Kubelet": "کیوب‌لِت",
}


# Common English leftovers from article bodies — never persist as "tech phonetics".
_CACHE_BLOCKLIST = {
    "ir", "io", "com", "org", "www", "http", "https",
    "error", "warning", "mode", "memory", "system", "parent", "wider",
    "root", "hard", "soft", "true", "false", "null", "none", "type",
    "file", "user", "name", "data", "code", "test", "info", "debug",
    "guaranteed", "burstable", "besteffort", "production", "maintenance",
    "isolation", "hierarchy", "unified", "ordering", "batch", "serving",
}


def _is_safe_cache_entry(key: str, value: str) -> bool:
    """Reject fragile auto-learned entries that cause systemic mispronunciation."""
    if not key or not value:
        return False
    if len(key) < 3:
        return False
    if len(value.strip()) < 2:
        return False
    if key.lower() in _CACHE_BLOCKLIST:
        return False
    # Person-like Titlecase single tokens with no digits (Josef, Bacik, …)
    if key.isalpha() and key[0].isupper() and key[1:].islower() and len(key) <= 8:
        # Allow known tech brands already in seed; block the rest from cache.
        if key not in BASE_TECHNICAL_DICTIONARY and key.lower() not in {
            k.lower() for k in BASE_TECHNICAL_DICTIONARY
        }:
            return False
    # Must contain at least one Persian letter in the pronunciation
    if not re.search(r'[\u0600-\u06FF]', value):
        return False
    return True


def get_merged_dictionary() -> Dict[str, str]:
    """Return base technical terms combined with auto-learned terms."""
    merged = dict(BASE_TECHNICAL_DICTIONARY)
    for key, value in DYNAMIC_CACHE.items():
        if _is_safe_cache_entry(key, value):
            merged[key] = value
    # Hard overrides always win (brand names, known fragile terms)
    merged.update(_DICTIONARY_OVERRIDES)
    return merged

def phonetize_acronym(acronym: str) -> str:
    """
    Automatically phonetize any all-caps English acronym into Persian sounds.
    e.g. HPA -> اچ‌پی‌ای, CSI -> سی‌اس‌آی, DRA -> دی‌آر‌ای, RBAC -> آر‌بی‌ای‌سی
    """
    parts = [LETTER_SOUNDS.get(ch, ch) for ch in acronym.upper()]
    return "\u200c".join(parts)


# Digraph/trigraph map for offline English→Persian phonetic fallback (Piper cannot read Latin).
_EN_PHONEME_RULES = [
    ("tion", "شِن"), ("sion", "ژِن"), ("ture", "چِر"), ("cious", "شِس"),
    ("ough", "اَف"), ("augh", "آف"), ("eigh", "ای"),
    ("sch", "ش"), ("chr", "کر"), (" thr", " ثر"),
    ("oo", "و"), ("ee", "ی"), ("ea", "ی"), ("oa", "و"), ("ai", "ای"), ("ay", "ای"),
    ("oy", "وی"), ("oi", "وی"), ("au", "آ"), ("aw", "آ"), ("ow", "او"), ("ou", "او"),
    ("ph", "ف"), ("wh", "و"), ("ch", "چ"), ("sh", "ش"), ("th", "ث"), ("ck", "ک"),
    ("qu", "کيو"), ("ng", "نگ"), ("kn", "ن"), ("wr", "ر"),
    ("a", "اَ"), ("e", "اِ"), ("i", "ای"), ("o", "اُ"), ("u", "اَ"),
    ("b", "ب"), ("c", "ک"), ("d", "د"), ("f", "ف"), ("g", "گ"), ("h", "ه"),
    ("j", "ج"), ("k", "ک"), ("l", "ل"), ("m", "م"), ("n", "ن"), ("p", "پ"),
    ("q", "کيو"), ("r", "ر"), ("s", "س"), ("t", "ت"), ("v", "و"), ("w", "و"),
    ("x", "کس"), ("y", "ی"), ("z", "ز"),
]


def approx_english_to_persian_phonetics(word: str) -> str:
    """
    Best-effort Latin→Persian phonetic spelling when dictionary/LLM miss a word.
    Goal: never send raw English letters to Persian Piper/fish-speech.
    """
    if not word:
        return ""
    raw = word.strip()
    # Pure acronyms / short all-caps
    letters_only = re.sub(r"[^A-Za-z]", "", raw)
    if letters_only.isupper() and 2 <= len(letters_only) <= 6:
        return phonetize_acronym(letters_only)

    s = letters_only.lower()
    out: List[str] = []
    i = 0
    while i < len(s):
        matched = False
        for eng, fa in _EN_PHONEME_RULES:
            if s.startswith(eng, i):
                out.append(fa)
                i += len(eng)
                matched = True
                break
        if not matched:
            i += 1
    spoken = "".join(out)
    # Soft separators for long compounds help Piper breathe
    if len(letters_only) >= 8 and "-" not in raw and "_" not in raw:
        # insert ZWNJ roughly mid-ish for readability: kubelet-like already handled
        pass
    return spoken or phonetize_acronym(letters_only[:6] or "X")


def strip_english_parentheticals(text: str) -> str:
    """
    FA posts often write «ایزوله‌سازی (Isolation)».
    Piper then tries to read the Latin inside parentheses and fails.
    Keep the Persian, drop Latin-only / Latin-heavy parentheses.
    """
    def _paren_repl(m: re.Match) -> str:
        inner = m.group(1).strip()
        latin = len(re.findall(r"[A-Za-z]", inner))
        arabic = len(re.findall(r"[\u0600-\u06FF]", inner))
        if latin > 0 and latin >= arabic:
            return " "
        return m.group(0)

    text = re.sub(r"\(([^)]{1,120})\)", _paren_repl, text)
    # Also drop bracketed Latin leftovers
    text = re.sub(r"\[([A-Za-z0-9 _./+\-]{1,80})\]", " ", text)
    return text


_ONES = [
    "صفر", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده",
    "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده",
]
_TENS = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
_HUNDREDS = [
    "", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد",
]


def int_to_persian_words(n: int) -> str:
    """Convert a non-negative integer to spoken Persian words (Piper-friendly)."""
    if n < 0:
        return "منفی " + int_to_persian_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] if ones == 0 else f"{_TENS[tens]} و {_ONES[ones]}"
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _HUNDREDS[hundreds] if rest == 0 else f"{_HUNDREDS[hundreds]} و {int_to_persian_words(rest)}"
    if n < 1000000:
        thousands, rest = divmod(n, 1000)
        head = "هزار" if thousands == 1 else f"{int_to_persian_words(thousands)} هزار"
        return head if rest == 0 else f"{head} و {int_to_persian_words(rest)}"
    return str(n)


def normalize_digits_for_speech(text: str) -> str:
    """
    Turn remaining ASCII/Persian digits into spoken Persian words.
    Piper often reads bare digits in an English-like or broken way.
    """
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    text = text.translate(trans)

    def _dec(m: re.Match) -> str:
        whole, frac = int(m.group(1)), int(m.group(2))
        return f"{int_to_persian_words(whole)} ممیز {int_to_persian_words(frac)}"

    text = re.sub(r'\b(\d+)[.\u066B٫](\d+)\b', _dec, text)
    text = re.sub(r'\b(\d+)\b', lambda m: int_to_persian_words(int(m.group(1))), text)
    return text


def normalize_numbers_versions_and_units(text: str) -> str:
    """Normalize versions, percentiles, percentages, and metrics to Persian words."""
    # Leading space in replacements prevents gluing onto the previous Persian word
    # e.g. «محدودیت‌های v1» must become «محدودیت‌های ورژن 1», never «محدودیت‌هایورژن 1».
    text = re.sub(
        r'(?:نسخه|ورژن)?\s*v(\d+)\.(\d+)(?:\.(\d+))?\b',
        lambda m: (
            f" نسخه {m.group(1)} ممیز {m.group(2)}"
            + (f" ممیز {m.group(3)}" if m.group(3) else "")
        ),
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'(?:نسخه|ورژن)?\s*v(\d+)\b',
        r' ورژن \1',
        text,
        flags=re.IGNORECASE,
    )
    # Bare «نسخه 1.35» (Persian label + ASCII decimal) — before punctuation can split it
    text = re.sub(
        r'(نسخه|ورژن)\s+(\d+)\.(\d+)(?:\.(\d+))?\b',
        lambda m: (
            f"{m.group(1)} {m.group(2)} ممیز {m.group(3)}"
            + (f" ممیز {m.group(4)}" if m.group(4) else "")
        ),
        text,
    )

    # Percentiles: p99 -> پی نود و نه, p95 -> پی نود و پنج
    text = re.sub(r'\bp99\b', 'پی نود و نه', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp95\b', 'پی نود و پنج', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp50\b', 'پی پنجاه', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp(\d+)\b', r'پی \1', text, flags=re.IGNORECASE)

    # Percentages: 99.9% -> 99.9 درصد
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 درصد', text)

    # Units of measurement
    text = re.sub(r'(\d+)\s*(?:ms|millisec)\b', r'\1 میلی‌ثانیه', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*(?:sec|seconds?)\b', r'\1 ثانیه', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*(?:Gbps|gbps)\b', r'\1 گیگابیت بر ثانیه', text)
    text = re.sub(r'(\d+)\s*(?:Mbps|mbps)\b', r'\1 مگابیت بر ثانیه', text)
    text = re.sub(r'(\d+)\s*(?:GB|GiB)\b', r'\1 گیگابایت', text)
    text = re.sub(r'(\d+)\s*(?:MB|MiB)\b', r'\1 مگابایت', text)
    text = re.sub(r'(\d+)\s*(?:KB|KiB)\b', r'\1 کیلوبایت', text)
    text = re.sub(r'(\d+)\s*(?:GHz)\b', r'\1 گیگاهرتز', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*(?:MHz)\b', r'\1 مگاهرتز', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*-?\s*bit\b', r'\1 بیتی', text, flags=re.IGNORECASE)

    return text


# Persian letter class for morphology-aware boundaries (Python \b is unreliable with ZWNJ).
_FA = r'[\u0600-\u06FF]'
_FA_SUFFIX = r'(?:\u200c?(?:هایی|های|ها|ی|ای))?'


def _fa_stem_pattern(stem: str) -> str:
    """Match a Persian stem plus common plural/ezāfe suffixes, not inside a longer word."""
    return rf'(?<!{_FA}){re.escape(stem)}({_FA_SUFFIX})(?!{_FA})'


def _attach_fa_suffix(replacement: str, suffix: str) -> str:
    """Re-attach a captured Persian suffix, inserting ZWNJ when needed."""
    if not suffix:
        return replacement
    if suffix.startswith("\u200c"):
        return replacement + suffix
    if suffix.startswith(("ها", "ی", "ای")) and not replacement.endswith("\u200c"):
        return replacement + "\u200c" + suffix
    return replacement + suffix


def _replace_fa_stem(text: str, stem: str, replacement: str) -> str:
    pattern = _fa_stem_pattern(stem)

    def _repl(m: re.Match) -> str:
        return _attach_fa_suffix(replacement, m.group(1) or "")

    return re.sub(pattern, _repl, text)


# Stems that TTS engines systematically misread (Piper/eSpeak/FaridNeural).
# Applied longest-conflict-first via ordered list; morphology covers ها/های/هایی/ی.
PERSIAN_TTS_STEM_FIXES = [
    # پادکست -> padkost; force long ā: پادکاست
    ("پادکست", "پادکاست"),
    # سرور -> sarvar (master); vocalize server reading
    ("سرور", "سِروِر"),
    # دواپس / دوآپس misread without kasra
    ("دوآپس", "دِواپس"),
    ("دواپس", "دِواپس"),
    # کانتینر / کلاستر / کلستر (common spelling without alif)
    ("کانتینر", "کانتِینِر"),
    ("کلاستر", "کِلاستِر"),
    ("کلستر", "کِلاستِر"),
    # کیوبلت often mumbled; keep hyphenated vocalized form
    ("کیوبلت", "کیوب‌لِت"),
    # Other Piper/eSpeak tech misreads
    ("استارت", "اِستارت"),
    ("ایویکت", "اِویکت"),
    ("اورکامیت", "اُورکِمیت"),
    ("اورکومیت", "اُورکِمیت"),
    ("رول‌اوت", "رول‌آوت"),
    ("رولاوت", "رول‌آوت"),
    ("پچ", "پَچ"),
    ("کرنل", "کِرنِل"),
    ("متریک", "مِتریک"),
    ("لاگ", "لَگ"),
    ("کش", "کَش"),
]


# Number-ninety contexts that must NOT be rewritten to «گره» (cluster node).
_NINETY_PROTECT_PATTERNS = [
    r'پی\s+نود(?:\s+و\s+(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه))?',
    r'نود\s+و\s+(?:یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه)',
    r'نود\s+درصد',
    r'نود\s+ممیز',
    r'نود\s+تا',
    # Units: «نود میلی‌ثانیه» must stay ninety, not become «گره میلی‌ثانیه»
    r'نود\s+میلی[\u200c\-]?ثانیه',
    r'نود\s+ثانیه',
    r'نود\s+دقیقه',
    r'نود\s+مگابایت',
    r'نود\s+گیگابایت',
    r'نود\s+مگابیت',
    r'نود\s+گیگابیت',
]


def _protect_ninety_number(text: str):
    """Mask Persian number-90 phrases so node→گره rewrites cannot corrupt them."""
    protected: List[str] = []

    def _mask(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"٪٪NIN{len(protected) - 1}٪٪"

    for pattern in _NINETY_PROTECT_PATTERNS:
        text = re.sub(pattern, _mask, text)
    return text, protected


def _restore_ninety_number(text: str, protected: List[str]) -> str:
    for idx, value in enumerate(protected):
        text = text.replace(f"٪٪NIN{idx}٪٪", value)
    return text


def normalize_persian_homographs(text: str) -> str:
    """
    Disambiguate Persian technical homographs for accurate speech synthesis.

    Critical behaviors:
    - Preserve number ninety («نود و نه»، «پی نود»، «نود درصد»).
    - Rewrite cluster-node «نود/نودها/نودهای/نودهایی» → «گره…» (TTS otherwise says navad).
    - Cover ZWNJ and non-ZWNJ plurals via stem+suffix morphology.
    """
    text, ninety_slots = _protect_ninety_number(text)

    for stem, replacement in PERSIAN_TTS_STEM_FIXES:
        text = _replace_fa_stem(text, stem, replacement)

    # Node → گره AFTER ninety protection (covers نودهایی which plain \\b rules missed).
    text = _replace_fa_stem(text, "نود", "گره")

    text = _restore_ninety_number(text, ninety_slots)
    return text

def _transliterate_unmapped_english_with_llm(words: List[str]) -> Dict[str, str]:
    """Call LLM to get phonetic Persian transliteration for novel English words."""
    if not words or not NEXUSLLM_API_KEY:
        return {}

    # Separate pure acronyms (all caps, 2-5 chars) which don't even need LLM
    novel_words = []
    acronym_results = {}
    for w in words:
        if w.isupper() and 2 <= len(w) <= 5:
            acronym_results[w] = phonetize_acronym(w)
        else:
            novel_words.append(w)

    if not novel_words:
        return acronym_results

    prompt = (
        "برای هر کدام از این اصطلاحات و کلمات انگلیسی حوزه فناوری، دقیقاً تلفظ و آوانگاری استاندارد آن را به خط فارسی بنویس. "
        "پاسخ را فقط به صورت یک آبجکت JSON معتبر بازگردان که کلیدها همان کلمات انگلیسی و مقادیر تلفظ فارسی باشند.\n\n"
        f"کلمات: {', '.join(novel_words[:30])}\n\n"
        'مثال خروجی: {"Karpenter": "کارپنتر", "vLLM": "وی اِل اِل اِم", "DeepSeek": "دیپ‌سیک"}'
    )

    payload = {
        "model": NEXUSLLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 600,
        "temperature": 0.1,
        "chat_template_kwargs": {"enable_thinking": False}
    }

    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        f"{NEXUSLLM_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    results = dict(acronym_results)
    try:
        with opener.open(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"].get("content", "").strip()
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'```$', '', content).strip()
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                llm_dict = json.loads(match.group(0))
                results.update(llm_dict)
    except Exception as e:
        print(f"[TextNormalizer] LLM transliteration warning: {e}")

    # Auto-learn: persist only safe novel transliterations
    if results:
        updated = False
        stored = 0
        for k, v in results.items():
            if k in DYNAMIC_CACHE or k in BASE_TECHNICAL_DICTIONARY or k in _DICTIONARY_OVERRIDES:
                continue
            if not _is_safe_cache_entry(k, v):
                continue
            DYNAMIC_CACHE[k] = v
            updated = True
            stored += 1
        if updated:
            _save_persistent_cache()
            print(f"[TextNormalizer] Auto-learned and cached {stored} new technical terms permanently.")

    return results

def normalize_mixed_persian_english_text(
    text: str,
    enable_auto_learning: bool = True,
    enable_llm_for_unknown: Optional[bool] = None
) -> str:
    """
    Self-Learning Normalization Pipeline for Persian Text-to-Speech (TTS).
    
    Transforms mixed English and Persian text into pure, fluent, natural
    Persian phonetic script. Auto-detects unknown English words and queries LLM
    once, caching them permanently so no manual dictionary maintenance is needed.
    """
    if enable_llm_for_unknown is not None:
        enable_auto_learning = enable_llm_for_unknown

    if not text:
        return ""

    # Step 1: Strip code fences, markdown syntax, links, and HTML
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Brand site spoken form (before generic URL stripping)
    text = re.sub(
        r'(?:https?://)?(?:www\.)?blog\.knowly\.ir\b',
        ' وب‌سایت بلاگ نولی ',
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\b(?:[\w-]+\.)+(?:com|org|net|io|ir|dev)/\S*', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    # Drop Latin parentheticals like «(Isolation)» before stripping ()
    text = strip_english_parentheticals(text)
    text = re.sub(r'[#*_\(\)\[\]\{\}<>"\']', ' ', text)

    # Step 2: Replace Known Technical Vocabulary (Base + Learned Cache)
    active_dict = get_merged_dictionary()
    # Case-insensitive lookup map for O(1) replaces
    lower_map = {k.lower(): v for k, v in active_dict.items()}
    sorted_keys = sorted(active_dict.keys(), key=len, reverse=True)
    if sorted_keys:
        pattern = re.compile(r'\b(' + '|'.join(re.escape(k) for k in sorted_keys) + r')\b', flags=re.IGNORECASE)

        def _repl(m: re.Match):
            return lower_map.get(m.group(0).lower(), m.group(0))

        text = pattern.sub(_repl, text)

    # Step 3: Normalize Numbers, Versions, and Units
    text = normalize_numbers_versions_and_units(text)

    # Step 4: Convert ALL remaining English to Persian phonetics (never leave Latin for Piper)
    remaining_english = list(set(re.findall(r'\b[a-zA-Z][a-zA-Z0-9+/\-]{1,}\b', text)))
    if remaining_english:
        unmapped = [
            w for w in remaining_english
            if w.lower() not in lower_map
        ]

        learned_dict: Dict[str, str] = {}
        if unmapped and enable_auto_learning:
            learned_dict = _transliterate_unmapped_english_with_llm(unmapped)

        # Build final replacement map: LLM → acronym → offline phonetic approx
        for w in remaining_english:
            wl = w.lower()
            if wl in lower_map:
                repl = lower_map[wl]
            elif w in learned_dict:
                repl = learned_dict[w]
            elif any(k.lower() == wl for k in learned_dict):
                repl = next(v for k, v in learned_dict.items() if k.lower() == wl)
            elif w.isupper() and 2 <= len(w) <= 6:
                repl = phonetize_acronym(w)
            else:
                repl = approx_english_to_persian_phonetics(w)
            if repl:
                text = re.sub(rf'\b{re.escape(w)}\b', repl, text)

        # Absolute last resort: purge any leftover Latin so Piper never sees it
        text = re.sub(r'\b[a-zA-Z][a-zA-Z0-9+/\-]*\b', '', text)

    # Step 5: Disambiguate Persian Homographs & Speech Engine Pronunciation Bugs
    # (پادکست→پادکاست، سرور→سِروِر، نود→گره with ninety-number protection, کلستر→کِلاستِر، …)
    text = normalize_persian_homographs(text)

    # Step 6: Digits → spoken Persian words (critical for Piper fa_IR-amir)
    text = normalize_digits_for_speech(text)

    # Step 7: Normalize Punctuation for Speech Breathing & Cadence
    # IMPORTANT: never split decimals like 1.35 → "1. 35" (breaks version reading).
    text = re.sub(r'[:؛–—]', '،', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s*([،!?])\s*', r'\1 ', text)
    text = re.sub(r'(?<!\d)\s*\.\s*(?!\d)', '. ', text)
    text = re.sub(r'([،!?])\s*\1+', r'\1', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)

    # Step 8: Final Typography Cleanup
    text = text.replace("ك", "ک").replace("ي", "ی")
    return text.strip()
