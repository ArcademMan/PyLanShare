"""Validazione input condivisa per ammstools."""

import ipaddress
import re


def is_valid_ipv4(text: str) -> bool:
    """Valida un indirizzo IPv4."""
    try:
        ipaddress.IPv4Address(text)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


def is_valid_interface_name(name: str) -> bool:
    """Valida un nome di interfaccia di rete (no caratteri pericolosi)."""
    if not name or len(name) > 256:
        return False
    # Solo lettere, numeri, spazi, trattini, parentesi, punti
    return bool(re.match(r'^[\w\s\-\.\(\)\[\]]+$', name))


def is_valid_hostname(name: str) -> bool:
    """Valida un hostname."""
    if not name or len(name) > 253:
        return False
    return bool(re.match(r'^[a-zA-Z0-9\-\.]+$', name))


def is_valid_mac(mac: str) -> bool:
    """Valida un MAC address (formato XX:XX:XX:XX:XX:XX o XX-XX-XX-XX-XX-XX)."""
    return bool(re.match(r'^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$', mac))
