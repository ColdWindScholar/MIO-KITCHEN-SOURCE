# src/core/verify_payload/payload_verifier.py
"""
Provides a high-level function to verify an Android update payload (payload.bin).

This module is the primary entry point for payload verification. It performs a
robust two-step check:
1. Data Integrity: Verifies the payload's file structure, data block hashes,
   and the consistency of its operations.
2. Cryptographic Authenticity: Verifies the payload's digital signature,
   if the payload is signed and a public key is provided.

On success, the main function returns True. On any failure, it prints a
detailed, localized error message to the console and raises a
`VerificationError`, ensuring that failures cannot be silently ignored.
"""

import os
import json
from typing import Optional, Dict, Tuple

from . import payload
from . import checker
from .error import PayloadError, VerificationError  # Import the custom exceptions

try:
    # Attempt to import for specific error checking.
    from cryptography.exceptions import InvalidSignature
except ImportError:
    # If cryptography is not installed, define a dummy exception class.
    # This prevents NameError exceptions in the `except` blocks.
    class InvalidSignature(Exception):
        pass


class _Localization:
    """A simple, self-contained class for loading localization strings."""
    def __init__(self, lang_code: str = 'English', lang_dir: Optional[str] = None) -> None:
        """
        Initializes the localization loader.

        Args:
            lang_code: The language code for the desired translation (e.g., 'English').
            lang_dir: The directory where language JSON files are stored.
        """
        if lang_dir is None:
            script_path = os.path.dirname(os.path.abspath(__file__))
            lang_dir = os.path.join(script_path, '..', '..', '..', 'bin', 'languages')

        self.data: Dict[str, str] = {}
        # Load English as a fallback first.
        default_lang_file = os.path.join(lang_dir, 'English.json')
        if os.path.exists(default_lang_file):
            try:
                with open(default_lang_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # Ignore errors in the default language file.

        # If a different language is requested, load it and update the defaults.
        if lang_code and lang_code.lower() != 'english':
            target_lang_file = os.path.join(lang_dir, f"{lang_code}.json")
            if os.path.exists(target_lang_file):
                try:
                    with open(target_lang_file, 'r', encoding='utf-8') as f:
                        lang_data = json.load(f)
                        self.data.update(lang_data)
                except (json.JSONDecodeError, IOError):
                    pass

    def __getattr__(self, name: str) -> str:
        """Allows accessing localization strings as attributes (e.g., lang.my_key)."""
        return self.data.get(name, f"<{name.upper()}_NOT_FOUND>")


def verify_payload(payload_path: str, public_key_path: Optional[str] = None, lang_code: str = 'English') -> bool:
    """
    Verifies the integrity and authenticity of a payload file.

    This function implements a robust two-step verification process. On success,
    it returns True. On any failure, it prints a detailed error message and
    raises a `VerificationError`.

    Args:
        payload_path: Path to the `payload.bin` file to be verified.
        public_key_path: Optional path to the public key for signature verification.
        lang_code: Language code for user-facing console messages.

    Returns:
        True on successful verification.

    Raises:
        VerificationError: If any part of the verification process fails.
    """
    lang = _Localization(lang_code=lang_code)

    if not os.path.exists(payload_path):
        message = lang.check_payload_not_found
        print(message)
        raise VerificationError(lang.return_summary_failure_payload_not_found)

    print(lang.check_started)

    # --- Step 1: Integrity Check & State Initialization ---
    print(lang.check_step_integrity)
    try:
        # Load the payload object once.
        payload_obj = payload.Payload(payload_path)

        # Create a single PayloadChecker instance. For the integrity check,
        # we explicitly disable the signature verification in the constructor.
        integrity_disabled_tests = (checker._CHECK_PAYLOAD_SIG,)
        payload_checker = checker.PayloadChecker(
            payload_obj,
            allow_unhashed=True,
            lang_code=lang_code,
            disabled_tests=integrity_disabled_tests
        )

        # This call checks everything except the signature and initializes
        # the checker's internal state (hashes, offsets, etc.).
        payload_checker.Run()
        print(lang.integrity_succeeded)

    except (PayloadError, Exception) as e:
        # If integrity check fails, it's a critical error.
        message = lang.integrity_failed.format(error=e)
        print(message)
        raise VerificationError(lang.return_summary_failure_integrity) from e

    # --- Step 2: Signature Authenticity Check ---
    print(lang.check_step_signature)

    # Case 1: User did not provide a key to verify with.
    if not public_key_path:
        print(lang.signature_skipped_no_pub_key)
        return True  # Success, as verification was not requested.

    # Case 2: The payload file itself is not signed.
    is_signed = payload_obj.manifest.signatures_size > 0
    if not is_signed:
        print(lang.signature_skipped_not_signed)
        return True  # Success, as there is no signature to verify.

    # Case 3: A key was provided and the payload is signed.
    # Perform the cryptographic verification.
    try:
        # We call the dedicated signature check method on the same checker
        # instance, which reuses the state calculated during the integrity check.
        payload_checker.CheckSignatures(report=None, pubkey_file_name=public_key_path)

        # If no exception was raised, the signature is valid.
        print(lang.signature_succeeded)

    except PayloadError as e:
        # Analyze the specific cause of the PayloadError to give a precise message.
        if isinstance(getattr(e, '__cause__', None), FileNotFoundError):
            message = lang.err_pubkey_not_found.format(pubkey_path=public_key_path)
            summary = lang.return_summary_failure_pubkey_not_found
        elif isinstance(getattr(e, '__cause__', None), InvalidSignature) or "mismatch" in str(e):
            message = lang.signature_failed_mismatch
            summary = lang.return_summary_failure_signature
        else:
            # For other crypto errors (e.g., bad key format).
            message = lang.signature_failed_generic.format(error=e)
            summary = lang.return_summary_failure_signature
        
        print(message)
        raise VerificationError(summary) from e

    except Exception as e:
        # Catch any other unexpected system errors during signature verification.
        message = lang.signature_failed_generic.format(error=f"An unexpected error occurred: {e}")
        print(message)
        raise VerificationError(lang.return_summary_failure_signature) from e

    # If we've reached this point, both integrity and signature checks passed.
    return True