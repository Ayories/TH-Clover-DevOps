#!/usr/bin/env python3
"""Create secrets.env for one environment, once, on the host (standard library only).

Usage: generate_secrets.py <environment-directory>

Values are written straight to root-only files and are never printed, so they do not pass
through Ansible, its logs or Git. An existing secrets.env is never overwritten.
"""
import hashlib
import os
import secrets
import string
import sys

# werkzeug's default scrypt parameters
SCRYPT_N, SCRYPT_R, SCRYPT_P = 32768, 8, 1


def werkzeug_scrypt_hash(password: str) -> str:
    """Return a hash that werkzeug.security.check_password_hash accepts."""
    salt = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt.encode(),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=132 * SCRYPT_N * SCRYPT_R * SCRYPT_P,
    ).hex()
    return f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${salt}${digest}"


def write_private(path: str, text: str) -> None:
    """Write a file readable by its owner only, replacing it atomically."""
    temporary = path + ".tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def main(directory: str) -> None:
    secrets_file = os.path.join(directory, "secrets.env")
    if os.path.exists(secrets_file):
        print("secrets.env already exists - left unchanged")
        return

    staff_password = secrets.token_urlsafe(18)
    values = {
        "POSTGRES_USER": "clover",
        # hexadecimal, so it is safe inside DATABASE_URL
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "POSTGRES_DB": "clover",
        "SECRET_KEY": secrets.token_hex(32),
        "STAFF_USERNAME": "staff",
        # single quotes stop Docker Compose from expanding the $ characters
        "STAFF_PASSWORD_HASH": f"'{werkzeug_scrypt_hash(staff_password)}'",
    }
    # The operator reads this once with sudo; it is not used by the application.
    write_private(os.path.join(directory, "staff-password.txt"), staff_password + "\n")
    # Written last: its presence means generation completed.
    write_private(secrets_file, "".join(f"{key}={value}\n" for key, value in values.items()))
    print("secrets.env created")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("usage: generate_secrets.py <existing environment directory>")
    main(sys.argv[1])
