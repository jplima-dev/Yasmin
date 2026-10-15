from __future__ import annotations

import getpass

from app.auth.security import hash_password


def main() -> None:
    password = getpass.getpass("Nova senha do Drive2: ")
    confirm = getpass.getpass("Repita a senha: ")
    if password != confirm:
        raise SystemExit("As senhas não coincidem.")
    print(hash_password(password))


if __name__ == "__main__":
    main()
