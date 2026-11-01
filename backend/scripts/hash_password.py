import sys

import bcrypt


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/hash_password.py '<password>'", file=sys.stderr)
        sys.exit(1)
    password = sys.argv[1].encode("utf-8")
    print(bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8"))


if __name__ == "__main__":
    main()
