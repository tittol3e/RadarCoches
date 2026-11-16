import argparse
import json
import uuid
from pathlib import Path

from .lab import Lab


def main():
    parser = argparse.ArgumentParser(description="DEMO / DATOS SINTÉTICOS — ingesta RadarCoches")
    parser.add_argument("command", choices=("demo", "revision", "simulate", "volume", "status", "extract-dlt", "publish", "consume", "export", "query"))
    parser.add_argument("--root", type=Path, default=Path("data/laboratorio"))
    parser.add_argument("--revision", type=int, choices=range(4), default=0)
    parser.add_argument("--api-a", default="http://127.0.0.1:8771")
    parser.add_argument("--api-b", default="http://127.0.0.1:8772")
    parser.add_argument("--bootstrap", default="127.0.0.1:9092")
    parser.add_argument("--query", choices=("counts", "prices", "history"), default="counts")
    args = parser.parse_args()
    lab = Lab(args.root)
    if args.command == "demo":
        lab = Lab(args.root / "demostraciones" / uuid.uuid4().hex)
        results = []
        for revision in range(4):
            result = lab.run_revision(revision)
            results.append(dict(revision=revision, unique_ads=result["counts"]["ads"], price_updates=result["counts"]["price_updates"]))
        output = dict(label="DEMO / DATOS SINTÉTICOS", mode="local_sqlite", revisions=results,
                      expected=[10, 12, 12, 12], passed=[r["unique_ads"] for r in results] == [10, 12, 12, 12],
                      evidence_dir=str(lab.root), kafka_executed=False, dlt_executed=False, duckdb_executed=False)
        args.root.mkdir(parents=True, exist_ok=True)
        (args.root / "resultado_revisiones.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    elif args.command == "revision":
        output = lab.run_revision(args.revision)
    elif args.command == "simulate":
        output = lab.prepare_revision(args.revision)
    elif args.command == "volume":
        output = lab.volume_demo()
    elif args.command == "status":
        output = lab.summary()
    else:
        from .distributed import consume, dlt_extract, export_analytics, publish, query_analytics
        if args.command == "extract-dlt":
            output = dlt_extract(args.root, {"demo_a": args.api_a, "demo_b": args.api_b})
        elif args.command == "publish":
            output = publish(args.root, args.bootstrap)
        elif args.command == "consume":
            output = consume(args.root, args.bootstrap)
        elif args.command == "export":
            output = export_analytics(args.root)
        else:
            output = query_analytics(args.root, args.query)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
