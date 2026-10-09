"""Doodle Phase 1 MVP entry point.

Launch:
    PYTHONPATH=src python -m doodle_mvp.main

Headless smoke test (no display needed):
    QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m doodle_mvp.main --self-check
"""

from __future__ import annotations

import argparse
import logging
import sys

from doodle_mvp.app.application import DoodleApplication


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Doodle — desktop panda companion (Phase 1 MVP)")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Build the app headlessly, verify idle animation, shut down, exit.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = DoodleApplication(sys.argv if argv is None else argv)
    if args.self_check:
        return app.self_check()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
