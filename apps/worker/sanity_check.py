import sys


def main() -> int:
    try:
        from packages.core.schemas.chart import PatientChart  # noqa: F401
        print("ok")
        return 0
    except Exception as e:
        print(f"sanity_check failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
