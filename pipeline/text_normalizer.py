import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional
from .config import BASE_DIR, NEXUSLLM_API_KEY, NEXUSLLM_BASE_URL, NEXUSLLM_MODEL

# Persistent auto-learning cache path
CACHE_DIR = BASE_DIR / "pipeline_data"
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

    # Core Roles & Practices
    "DevOps": "دوآپس",
    "SREs": "مهندسان اس‌آر‌ای",
    "SRE": "اس‌آر‌ای",
    "Site Reliability Engineering": "مهندسی قابلیت اطمینان سایت",
    "CI/CD": "سی‌آی‌سی‌دی",
    "GitOps": "گیت‌اپس",
    "FinOps": "فین‌اپس",
    "SysAdmin": "سیس‌ادمین",

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
    "Kubelet": "کیوبلت",
    "Kubeadm": "کیوب‌ادمین",
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
    "File Capabilities": "فایل کیپبیلیتیز",
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

def get_merged_dictionary() -> Dict[str, str]:
    """Return base technical terms combined with auto-learned terms."""
    merged = dict(BASE_TECHNICAL_DICTIONARY)
    merged.update(DYNAMIC_CACHE)
    return merged

def phonetize_acronym(acronym: str) -> str:
    """
    Automatically phonetize any all-caps English acronym into Persian sounds.
    e.g. HPA -> اچ‌پی‌ای, CSI -> سی‌اس‌آی, DRA -> دی‌آر‌ای, RBAC -> آر‌بی‌ای‌سی
    """
    parts = [LETTER_SOUNDS.get(ch, ch) for ch in acronym.upper()]
    return "\u200c".join(parts)

def normalize_numbers_versions_and_units(text: str) -> str:
    """Normalize versions, percentiles, percentages, and metrics to Persian words."""
    # Versions: نسخه v1.35 or v1.35 -> نسخه یک ممیز سی و پنج
    text = re.sub(
        r'(?:نسخه|ورژن)?\s*v(\d+)\.(\d+)(?:\.(\d+))?\b',
        lambda m: f"نسخه {m.group(1)} ممیز {m.group(2)}" + (f" ممیز {m.group(3)}" if m.group(3) else ""),
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(r'(?:نسخه|ورژن)?\s*v(\d+)\b', r'ورژن \1', text, flags=re.IGNORECASE)

    # Percentiles: p99 -> پی نود و نه, p95 -> پی نود و پنج
    text = re.sub(r'\bp99\b', 'پی نود و نه', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp95\b', 'پی نود و پنج', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp50\b', 'پی پنجاه', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp(\d+)\b', r'پی \1', text, flags=re.IGNORECASE)

    # Percentages: 99.9% -> نود و نه و نه دهم درصد
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

# Persian Homographs & Vowel Disambiguation for Piper/eSpeak
# Solves eSpeak mispronunciations (e.g. پادکست -> padkost, سرور -> sarvar, نود -> navad)
PERSIAN_HOMOGRAPH_FIXES: Dict[str, str] = {
    # Fix 'پادکست' which eSpeak reads as 'padkost' -> change to 'پادکاست' with clear long vowel
    r'\bپادکست\b': 'پادکاست',
    r'\bپادکست‌ها\b': 'پادکاست‌ها',
    r'\bپادکستهای\b': 'پادکاست‌های',
    r'\bپادکستی\b': 'پادکاستی',

    # Fix 'سرور' which eSpeak reads as 'sarvar' (master) -> vocalize to 'سِروِر'
    r'\bسرور\b': 'سِروِر',
    r'\bسرورها\b': 'سِروِرها',
    r'\bسرورهای\b': 'سِروِرهای',
    r'\bسروری\b': 'سِروِری',

    # Fix 'نود' which eSpeak reads as 'navad' (the number 90) -> use 'گره'
    r'\bنودها\b': 'گره‌ها',
    r'\bنودهای\b': 'گره‌های',
    r'\bنود\b': 'گره',

    # Fix 'دواپس' which eSpeak reads as 'davapes' -> 'دِواپس'
    r'\bدواپس\b': 'دِواپس',

    # Fix 'کانتینر' -> 'کانتِینِر'
    r'\bکانتینر\b': 'کانتِینِر',
    r'\bکانتینرها\b': 'کانتِینِرها',
    r'\bکانتینرهای\b': 'کانتِینِرهای',

    # Fix 'کلاستر' -> 'کِلاستِر'
    r'\bکلاستر\b': 'کِلاستِر',
    r'\bکلاسترها\b': 'کِلاستِرها',
    r'\bکلاسترهای\b': 'کِلاستِرهای',
}

def normalize_persian_homographs(text: str) -> str:
    """Disambiguate common Persian technical homographs for accurate speech synthesis."""
    for pattern, replacement in PERSIAN_HOMOGRAPH_FIXES.items():
        text = re.sub(pattern, replacement, text)
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

    # Auto-learn: persist any new learned words into DYNAMIC_CACHE
    if results:
        updated = False
        for k, v in results.items():
            if k not in DYNAMIC_CACHE and v and len(v) > 1:
                DYNAMIC_CACHE[k] = v
                updated = True
        if updated:
            _save_persistent_cache()
            print(f"[TextNormalizer] Auto-learned and cached {len(results)} new technical terms permanently.")

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
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[#*_\(\)\[\]\{\}<>"\']', ' ', text)

    # Step 2: Replace Known Technical Vocabulary (Base + Learned Cache)
    active_dict = get_merged_dictionary()
    sorted_keys = sorted(active_dict.keys(), key=len, reverse=True)
    if sorted_keys:
        pattern = re.compile(r'\b(' + '|'.join(re.escape(k) for k in sorted_keys) + r')\b', flags=re.IGNORECASE)
        def _repl(m: re.Match):
            word = m.group(0)
            for k, v in active_dict.items():
                if k.lower() == word.lower():
                    return v
            return word
        text = pattern.sub(_repl, text)

    # Step 3: Normalize Numbers, Versions, and Units
    text = normalize_numbers_versions_and_units(text)

    # Step 4: Auto-detect Any Remaining English Words & Acronyms
    remaining_english = list(set(re.findall(r'\b[a-zA-Z]{2,}\b', text)))
    if remaining_english:
        # Check against active_dict again (case-insensitive)
        unmapped = [
            w for w in remaining_english
            if not any(k.lower() == w.lower() for k in active_dict)
        ]

        if unmapped and enable_auto_learning:
            learned_dict = _transliterate_unmapped_english_with_llm(unmapped)
            for en_word, fa_pron in learned_dict.items():
                w_pat = r'\b' + re.escape(en_word) + r'\b'
                text = re.sub(w_pat, fa_pron, text, flags=re.IGNORECASE)

        # Fallback for pure all-caps acronyms that weren't caught
        text = re.sub(
            r'\b[A-Z]{2,5}\b',
            lambda m: phonetize_acronym(m.group(0)),
            text
        )

        # Remove any lingering standalone English letters to avoid TTS glitches
        text = re.sub(r'\b[a-zA-Z]+\b', '', text)

    # Step 5: Disambiguate Persian Homographs & Speech Engine Pronunciation Bugs
    # (e.g. transforms پادکست -> پادکاست, سرور -> سِروِر, نود -> گره)
    text = normalize_persian_homographs(text)

    # Step 6: Normalize Punctuation for Speech Breathing & Cadence
    # Convert colons, semicolons, and dashes into commas for natural breathing pauses
    text = re.sub(r'[:؛–—]', '،', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s*([،\.!?])\s*', r'\1 ', text)
    text = re.sub(r'([،\.!?])\s*\1+', r'\1', text)
    text = re.sub(r'\n+', ' ', text)

    # Step 6: Final Typography Cleanup
    text = text.replace("ك", "ک").replace("ي", "ی")
    return text.strip()
