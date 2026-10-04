"""Build curated bridge assets, optionally publish their metadata to shared PostgreSQL."""
import argparse
import json
from pathlib import Path
from floodbeacon.imagery import CATALOG, build_catalog, publish_catalog, validate_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Publish complete case metadata after building')
    parser.add_argument('--publish-only', action='store_true', help='Publish checked-in catalog without processing dependencies')
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text()) if args.publish_only else build_catalog(Path(__file__).resolve().parents[1])
    validate_catalog(catalog)
    if args.publish or args.publish_only:
        print(json.dumps(publish_catalog(catalog), indent=2))
    else:
        print(json.dumps({'catalog': str(CATALOG), 'cases': [r['case']['id'] for r in catalog['cases']]}, indent=2))


if __name__ == '__main__':
    main()
