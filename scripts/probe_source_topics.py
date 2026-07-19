#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.schema import connect, init_db
from dst_wiki_db.source_topic_probes import probe_source_topics


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Probe representative wiki, competitor, and official topic URLs."
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/source_topic_probes.json"),
    )
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    payload = probe_source_topics(conn, timeout=args.timeout)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
