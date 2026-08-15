# src/sonus/cli/main.py
from __future__ import annotations

import argparse
import sys

from sonus.cli.probe import run_probe
from sonus.cli.send import run_send
from sonus.cli.sniff import run_sniff

DEFAULT_SERVICE_UUID = "956c7b26-d49a-4ba8-b03f-b17d393cb6e2"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sonus")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe", help="discover the RFCOMM channel and connect")
    probe_parser.add_argument("--mac", required=True)
    probe_parser.add_argument("--service-uuid", default=DEFAULT_SERVICE_UUID)

    sniff_parser = subparsers.add_parser("sniff", help="log raw received bytes to a file")
    sniff_parser.add_argument("--mac", required=True)
    sniff_parser.add_argument("--channel", type=int, required=True)
    sniff_parser.add_argument("--out", required=True)

    send_parser = subparsers.add_parser("send", help="send a raw frame and print the response")
    send_parser.add_argument("--mac", required=True)
    send_parser.add_argument("--channel", type=int, required=True)
    send_parser.add_argument("--type", type=lambda s: int(s, 0), required=True, dest="msg_type")
    send_parser.add_argument("--payload", default="", help="hex-encoded payload bytes")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "probe":
        print(run_probe(args.mac, args.service_uuid))
    elif args.command == "sniff":
        try:
            count = run_sniff(args.mac, args.channel, args.out)
        except KeyboardInterrupt:
            print("stopped")
            return 0
        print(f"logged {count} frames to {args.out}")
    elif args.command == "send":
        print(run_send(args.mac, args.channel, msg_type=args.msg_type, payload_hex=args.payload))

    return 0


if __name__ == "__main__":
    sys.exit(main())
