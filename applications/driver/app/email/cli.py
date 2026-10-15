from __future__ import annotations

import argparse
import json

from app.email.gmail import GmailService


def main() -> None:
    parser = argparse.ArgumentParser(description="Ferramentas Gmail do Drive2")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth", help="Autorizar o Drive2 no Gmail")
    run = sub.add_parser("archive", help="Arquivar e-mails elegíveis")
    run.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    service = GmailService()
    if args.command == "auth":
        service.authenticate(open_browser=True)
        print("Gmail autorizado com sucesso.")
    elif args.command == "archive":
        print(json.dumps(service.run_archive(args.limit), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
