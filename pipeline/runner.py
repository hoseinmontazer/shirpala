import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from .config import DAILY_MAX_POSTS, SCHEDULE_TIME, AUDIT_MIN_SCORE
from .db import init_db, get_stats
from .fetcher import fetch_new_articles
from .translator import translate_article
from .auditor import audit_and_clean_post, normalize_persian_text
from .publisher import publish_post

def run_pipeline(limit: int = DAILY_MAX_POSTS):
    """Execute one complete cycle of fetching, translating, auditing, and publishing."""
    print("=" * 60)
    print(f"🚀 Shirpala Pipeline Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📋 Configuration: Daily Limit={limit}, Min Audit Score={AUDIT_MIN_SCORE}")
    print("=" * 60)

    init_db()

    # Step 1: Fetch new candidate articles
    print("\n[Step 1/4] Fetching new articles from configured sources...")
    articles = fetch_new_articles(limit_per_source=2)
    if not articles:
        print("ℹ️ No new unread articles found across sources.")
        return

    # Limit to daily quota
    selected_articles = articles[:limit]
    print(f"✅ Selected {len(selected_articles)} article(s) for processing today.\n")

    published_count = 0
    flagged_count = 0

    for idx, article in enumerate(selected_articles, 1):
        print("-" * 50)
        print(f"Processing ({idx}/{len(selected_articles)}): {article['title']}")
        print(f"Source: {article['source_name']} | URL: {article['url']}")

        # Step 2: Translate & Adapt
        print("[Step 2/4] Translating and adapting into Persian...")
        try:
            translation = translate_article(article)
        except Exception as e:
            print(f"❌ Translation error: {e}")
            continue

        # Step 3: Check & Audit First
        print("[Step 3/4] Running Quality & Schema Audit...")
        is_approved, score, audited_post, audit_notes = audit_and_clean_post(
            post_data=translation,
            source_url=article["url"],
            min_score=AUDIT_MIN_SCORE
        )

        for note in audit_notes:
            print(f"  • {note}")

        # Step 4: Publish to Hugo
        print(f"[Step 4/4] Publishing to Hugo (Approved: {is_approved}, Score: {score}/100)...")
        file_path = publish_post(
            post_data=audited_post,
            is_approved=is_approved,
            audit_score=score,
            audit_notes=audit_notes,
            article_id=article.get("article_id")
        )

        if is_approved:
            published_count += 1
            print(f"🎉 Successfully Published: {file_path.name}")
        else:
            flagged_count += 1
            print(f"⚠️ Flagged as Draft for Manual Review: {file_path.name}")

    print("\n" + "=" * 60)
    print("📊 Pipeline Execution Summary:")
    print(f"  • Processed: {len(selected_articles)}")
    print(f"  • Published (Live): {published_count}")
    print(f"  • Flagged (Draft): {flagged_count}")
    print("=" * 60)

def run_scheduled_daemon(schedule_time: str = SCHEDULE_TIME):
    """Run pipeline daily at the designated time (e.g. 07:00 UTC)."""
    print(f"⏰ Shirpala Daily Daemon active. Scheduled daily at {schedule_time} UTC.")
    print("Running initial execution on startup...")
    run_pipeline()

    # Simple scheduler loop
    while True:
        now_time = datetime.utcnow().strftime("%H:%M")
        if now_time == schedule_time:
            print(f"\n⏰ Triggering daily scheduled run at {now_time} UTC...")
            run_pipeline()
            time.sleep(65)  # Avoid duplicate trigger in the same minute
        time.sleep(30)

def audit_single_file(file_path_str: str):
    """Audit an existing markdown file in the content directory."""
    path = Path(file_path_str)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    raw_text = path.read_text(encoding="utf-8")
    # Extract frontmatter and body
    body = raw_text
    title = path.stem
    desc = ""
    tags = []

    # Simple frontmatter extractor for TOML or YAML
    if raw_text.startswith("+++"):
        parts = raw_text.split("+++", 2)
        if len(parts) >= 3:
            fm_text, body = parts[1], parts[2]
            for line in fm_text.splitlines():
                if line.startswith("title ="):
                    title = line.split("=", 1)[1].strip().strip('"\'')
                elif line.startswith("description ="):
                    desc = line.split("=", 1)[1].strip().strip('"\'')
    elif raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            fm_text, body = parts[1], parts[2]
            for line in fm_text.splitlines():
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"\'')
                elif line.startswith("link:"):
                    desc = line.split(":", 1)[1].strip().strip('"\'')

    post_data = {
        "title": title,
        "description": desc,
        "slug": path.stem,
        "tags": tags,
        "categories": ["Tech"],
        "content_markdown": body
    }

    is_approved, score, cleaned, notes = audit_and_clean_post(post_data)
    print(f"\n🔍 Audit Report for {path.name}:")
    print(f"Score: {score}/100 | Approved: {is_approved}")
    for n in notes:
        print(f"  • {n}")

def show_stats():
    """Display statistics from SQLite."""
    init_db()
    stats = get_stats()
    print("\n📊 Shirpala Pipeline Database Statistics:")
    if not stats:
        print("  (Database is empty. No articles processed yet.)")
    else:
        for status, count in stats.items():
            print(f"  • {status}: {count}")

def main():
    parser = argparse.ArgumentParser(description="Shirpala Daily Automated Ingestion & Publishing Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run the pipeline once")
    run_parser.add_argument("--limit", type=int, default=DAILY_MAX_POSTS, help="Maximum posts to process")

    # Command: schedule (daemon)
    sched_parser = subparsers.add_parser("schedule", help="Run continuously as a daily daemon")
    sched_parser.add_argument("--time", type=str, default=SCHEDULE_TIME, help="Daily time in HH:MM UTC")

    # Command: audit-file
    audit_parser = subparsers.add_parser("audit-file", help="Audit an existing markdown file")
    audit_parser.add_argument("file", type=str, help="Path to markdown file")

    # Command: stats
    subparsers.add_parser("stats", help="Show pipeline database statistics")

    args = parser.parse_args()

    if args.command == "run" or args.command is None:
        limit = getattr(args, "limit", DAILY_MAX_POSTS)
        run_pipeline(limit=limit)
    elif args.command == "schedule":
        run_scheduled_daemon(args.time)
    elif args.command == "audit-file":
        audit_single_file(args.file)
    elif args.command == "stats":
        show_stats()

if __name__ == "__main__":
    main()
