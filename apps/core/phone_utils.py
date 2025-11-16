# core/phone_utils.py  (create this helper)
import re
import phonenumbers

def normalize_local_digits(s: str | None) -> str | None:
    if s is None:
        return None
    return re.sub(r"\D", "", s)

def to_e164(phone_raw: str, default_region: str = "CM") -> str:
    """
    Accepts either local/national digits or already-E.164.
    Returns a strict E.164 string like '+2376xxxxxxx' or raises ValueError.
    """
    if not phone_raw:
        raise ValueError("empty phone")

    # If it already starts with '+', try parsing directly
    if str(phone_raw).strip().startswith("+"):
        num = phonenumbers.parse(phone_raw, None)
        if not phonenumbers.is_possible_number(num) or not phonenumbers.is_valid_number(num):
            raise ValueError("invalid e164")
        return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)

    # Else treat as national digits in default_region
    nat = normalize_local_digits(phone_raw)
    num = phonenumbers.parse(nat, default_region or "CM")
    if not phonenumbers.is_possible_number(num) or not phonenumbers.is_valid_number(num):
        raise ValueError("invalid national number")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
