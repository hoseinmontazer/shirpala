import re
import json
from typing import Dict, List, Optional
from .config import NEXUSLLM_API_KEY, NEXUSLLM_BASE_URL, NEXUSLLM_MODEL

# Comprehensive Technical Dictionary: English -> Persian Phonetic
# Ordered conceptually; will be compiled with longest matches first.
TECHNICAL_DICTIONARY: Dict[str, str] = {
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

    # Cloud Providers
    "AWS": "ای‌دبلیواس",
    "GCP": "جی‌سی‌پی",
    "Azure": "آژور",

    # Common Programming Languages
    "Golang": "زبان گو",
    "Go": "گو",
    "Rust": "راست",
    "Python": "پایتون",
    "Bash": "بش",
}

# Pre-compile sorted technical terms (longer terms first to prevent partial replacement)
_SORTED_PATTERNS = sorted(TECHNICAL_DICTIONARY.keys(), key=len, reverse=True)
_TECH_REGEX = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in _SORTED_PATTERNS) + r')\b',
    flags=re.IGNORECASE
)

def _replace_technical_term(match: re.Match) -> str:
    word = match.group(0)
    # Case-insensitive lookup in dictionary
    for k, v in TECHNICAL_DICTIONARY.items():
        if k.lower() == word.lower():
            return v
    return word

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

    # Units of measurement (ordered carefully)
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

def _transliterate_unmapped_english_with_llm(words: List[str]) -> Dict[str, str]:
    """Call LLM to get phonetic Persian transliteration for unknown English words."""
    if not words or not NEXUSLLM_API_KEY:
        return {}

    prompt = (
        "برای هر کدام از این اصطلاحات و کلمات انگلیسی، دقیقاً تلفظ و آوانگاری آن را به خط فارسی بنویس. "
        "پاسخ را فقط به صورت یک آبجکت JSON معتبر بازگردان که کلیدها همان کلمات انگلیسی و مقادیر تلفظ فارسی باشند.\n\n"
        f"کلمات: {', '.join(words[:25])}\n\n"
        'مثال خروجی: {"Throttling": "تراتلینگ", "RateLimiting": "ریت لیمیتینگ"}'
    )

    payload = {
        "model": NEXUSLLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
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

    try:
        with opener.open(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"].get("content", "").strip()
            # Clean markdown JSON fences
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'```$', '', content).strip()
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                return json.loads(match.group(0))
    except Exception as e:
        print(f"[TextNormalizer] LLM transliteration warning: {e}")

    return {}

def normalize_mixed_persian_english_text(
    text: str,
    enable_llm_for_unknown: bool = True
) -> str:
    """
    Primary Normalization Pipeline for Persian Text-to-Speech (TTS).
    
    Transforms mixed English and Persian text into pure, fluent, natural
    Persian phonetic script suitable for Piper and Neural speech synthesizers.
    """
    if not text:
        return ""

    # Step 1: Strip code fences, markdown syntax, links, and HTML
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[#*_\(\)\[\]\{\}<>"\']', ' ', text)

    # Step 2: Replace Known Technical Vocabulary via Regex Dictionary
    text = _TECH_REGEX.sub(_replace_technical_term, text)

    # Step 3: Normalize Numbers, Versions, and Units
    text = normalize_numbers_versions_and_units(text)

    # Step 4: Handle Unmapped English Words
    remaining_english = list(set(re.findall(r'\b[a-zA-Z]{2,}\b', text)))
    if remaining_english:
        if enable_llm_for_unknown and len(remaining_english) <= 20:
            llm_replacements = _transliterate_unmapped_english_with_llm(remaining_english)
            for en_word, fa_pron in llm_replacements.items():
                pattern = r'\b' + re.escape(en_word) + r'\b'
                text = re.sub(pattern, fa_pron, text, flags=re.IGNORECASE)

        # Remove any lingering standalone English letters to avoid TTS glitches
        text = re.sub(r'\b[a-zA-Z]+\b', '', text)

    # Step 5: Normalize Punctuation for Speech Breathing & Cadence
    # Convert colons, semicolons, and dashes into commas for natural breathing pauses
    text = re.sub(r'[:؛–—]', '،', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s*([،\.!?])\s*', r'\1 ', text)
    text = re.sub(r'([،\.!?])\s*\1+', r'\1', text)
    text = re.sub(r'\n+', ' ', text)

    # Step 6: Final Typography Cleanup
    text = text.replace("ك", "ک").replace("ي", "ی")
    return text.strip()
