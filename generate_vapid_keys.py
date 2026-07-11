"""Generate a VAPID (Voluntary Application Server Identification) key pair
for Web Push — Stage 7.

Run this once per deployment and put the output in your environment
(.env locally, project env vars on Vercel). Re-running it produces a new
key pair, which invalidates every existing push subscription — anyone
who'd already clicked "Enable notifications" would need to click it again.

Usage:
    python generate_vapid_keys.py
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def generate_vapid_keys():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    # Raw 32-byte private scalar, base64url — the format pywebpush/py_vapid
    # accept directly as VAPID_PRIVATE_KEY (no PEM wrapping needed).
    private_value = private_key.private_numbers().private_value
    private_b64 = _b64url(private_value.to_bytes(32, "big"))

    # Uncompressed EC point (0x04 || X || Y), base64url — this is the exact
    # format the browser's PushManager.subscribe({ applicationServerKey })
    # expects for VAPID_PUBLIC_KEY.
    public_key_der = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = _b64url(public_key_der)

    return private_b64, public_b64


if __name__ == "__main__":
    private_b64, public_b64 = generate_vapid_keys()
    print("Generated a new VAPID key pair. Add these to your environment:\n")
    print(f"VAPID_PRIVATE_KEY={private_b64}")
    print(f"VAPID_PUBLIC_KEY={public_b64}")
    print(f"VAPID_CLAIM_EMAIL=mailto:you@example.com   # change to a real contact address")
    print(
        "\nVAPID_PRIVATE_KEY is a secret — keep it out of git, same as SECRET_KEY. "
        "VAPID_PUBLIC_KEY is safe to expose (the app already sends it to the browser)."
    )
