import hashlib
import hmac
from typing import Any, Dict, List, Tuple

import base58
from Crypto.Hash import keccak
from ecdsa import SECP256k1, SigningKey
from eth_utils import to_checksum_address
from nacl.signing import SigningKey as Ed25519SigningKey

from utils import CHAIN_DEFAULTS, get_seed_analysis, parse_bip32_path

SECP256K1_ORDER = SECP256k1.order


def _keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def _double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _hmac_sha512(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha512).digest()


def _ser32(i: int) -> bytes:
    return i.to_bytes(4, "big")


def _ser256(i: int) -> bytes:
    return i.to_bytes(32, "big")


def _parse256(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _fingerprint_from_pubkey(pub_uncompressed: bytes) -> bytes:
    sha = hashlib.sha256(pub_uncompressed).digest()
    ripe = hashlib.new("ripemd160", sha).digest()
    return ripe[:4]


def _ensure_uncompressed_secp_pub(pub_bytes: bytes) -> bytes:
    if len(pub_bytes) == 65 and pub_bytes[0] == 0x04:
        return pub_bytes
    raise ValueError("Expected a 65-byte uncompressed secp256k1 public key starting with 0x04.")


def _secp_public_keys_from_private_key(priv_key_bytes: bytes) -> Tuple[bytes, bytes]:
    sk = SigningKey.from_string(priv_key_bytes, curve=SECP256k1)
    vk = sk.verifying_key
    raw = vk.to_string()  # 64 bytes = x || y
    x = raw[:32]
    y = raw[32:]
    uncompressed = b"\x04" + raw
    compressed_prefix = b"\x02" if (y[-1] % 2 == 0) else b"\x03"
    compressed = compressed_prefix + x
    return uncompressed, compressed


def evm_address_from_uncompressed_pub(pub_bytes: bytes) -> Dict[str, Any]:
    pub_bytes = _ensure_uncompressed_secp_pub(pub_bytes)
    body = pub_bytes[1:]
    digest = _keccak256(body)
    addr_bytes = digest[-20:]
    raw_hex = "0x" + addr_bytes.hex()
    checksum = to_checksum_address(raw_hex)
    return {
        "public_key_body_hex": body.hex(),
        "keccak_hex": digest.hex(),
        "address_bytes": addr_bytes,
        "address_hex_lower": raw_hex,
        "address_checksum": checksum,
    }


def tron_address_from_uncompressed_pub(pub_bytes: bytes) -> Dict[str, Any]:
    pub_bytes = _ensure_uncompressed_secp_pub(pub_bytes)
    body = pub_bytes[1:]
    digest = _keccak256(body)
    addr20 = digest[-20:]
    tron_hex_bytes = b"\x41" + addr20
    checksum = _double_sha256(tron_hex_bytes)[:4]
    base58_addr = base58.b58encode(tron_hex_bytes + checksum).decode("utf-8")
    return {
        "public_key_body_hex": body.hex(),
        "keccak_hex": digest.hex(),
        "address20_hex": addr20.hex(),
        "tron_hex": tron_hex_bytes.hex(),
        "base58check_checksum_hex": checksum.hex(),
        "address_base58": base58_addr,
    }


def solana_pubkey_and_address_from_private_key(priv_key_bytes: bytes) -> Dict[str, Any]:
    if len(priv_key_bytes) != 32:
        raise ValueError("Solana educational lane expects a 32-byte ed25519 private key seed.")
    signing_key = Ed25519SigningKey(priv_key_bytes)
    verify_key = signing_key.verify_key
    pub_bytes = verify_key.encode()
    address = base58.b58encode(pub_bytes).decode("utf-8")
    return {
        "public_key_bytes": pub_bytes,
        "public_key_hex": pub_bytes.hex(),
        "address_base58": address,
    }


def validate_ed25519_path(path: str) -> None:
    segments = parse_bip32_path(path)
    for seg in segments:
        if not seg["hardened"]:
            raise ValueError("ed25519 / SLIP-0010 では hardened derivation のみをサポートします。")


def _master_key_secp256k1(seed_bytes: bytes) -> Tuple[bytes, bytes]:
    i = _hmac_sha512(b"Bitcoin seed", seed_bytes)
    il, ir = i[:32], i[32:]
    il_int = _parse256(il)
    if il_int == 0 or il_int >= SECP256K1_ORDER:
        raise ValueError("Invalid master key generated for secp256k1.")
    return il, ir


def _ckd_priv_secp256k1(parent_priv: bytes, parent_chain_code: bytes, index: int) -> Tuple[bytes, bytes]:
    hardened = index >= 0x80000000

    if hardened:
        data = b"\x00" + parent_priv + _ser32(index)
    else:
        parent_pub_compressed = _secp_public_keys_from_private_key(parent_priv)[1]
        data = parent_pub_compressed + _ser32(index)

    i = _hmac_sha512(parent_chain_code, data)
    il, ir = i[:32], i[32:]
    il_int = _parse256(il)
    parent_int = _parse256(parent_priv)

    if il_int >= SECP256K1_ORDER:
        raise ValueError("Invalid child key: IL >= curve order.")

    child_int = (il_int + parent_int) % SECP256K1_ORDER
    if child_int == 0:
        raise ValueError("Invalid child key: derived zero private key.")

    return _ser256(child_int), ir


def _master_key_ed25519(seed_bytes: bytes) -> Tuple[bytes, bytes]:
    i = _hmac_sha512(b"ed25519 seed", seed_bytes)
    return i[:32], i[32:]


def _ckd_priv_ed25519(parent_priv: bytes, parent_chain_code: bytes, index: int) -> Tuple[bytes, bytes]:
    if index < 0x80000000:
        raise ValueError("ed25519 / SLIP-0010 では hardened derivation のみをサポートします。")
    data = b"\x00" + parent_priv + _ser32(index)
    i = _hmac_sha512(parent_chain_code, data)
    return i[:32], i[32:]


def _ctx_to_step_data_secp(
    priv_bytes: bytes,
    chain_code: bytes,
    depth: int,
    path_so_far: str,
    label: str,
    index_repr: str,
) -> Dict[str, Any]:
    pub_uncompressed, pub_compressed = _secp_public_keys_from_private_key(priv_bytes)
    return {
        "path": path_so_far,
        "label": label,
        "index_repr": index_repr,
        "depth": depth,
        "private_key_bytes": priv_bytes,
        "private_key_hex": priv_bytes.hex(),
        "public_key_uncompressed_bytes": pub_uncompressed,
        "public_key_uncompressed_hex": pub_uncompressed.hex(),
        "public_key_compressed_bytes": pub_compressed,
        "public_key_compressed_hex": pub_compressed.hex(),
        "public_key_bytes": pub_uncompressed,
        "public_key_hex": pub_uncompressed.hex(),
        "public_key_display_label": "公開鍵 (65-byte, uncompressed hex)",
        "public_key_display_hex": pub_uncompressed.hex(),
        "chain_code_bytes": chain_code,
        "chain_code_hex": chain_code.hex(),
        "fingerprint_hex": _fingerprint_from_pubkey(pub_uncompressed).hex(),
    }


def _ctx_to_step_data_ed25519(
    priv_bytes: bytes,
    chain_code: bytes,
    depth: int,
    path_so_far: str,
    label: str,
    index_repr: str,
) -> Dict[str, Any]:
    sol = solana_pubkey_and_address_from_private_key(priv_bytes)
    return {
        "path": path_so_far,
        "label": label,
        "index_repr": index_repr,
        "depth": depth,
        "private_key_bytes": priv_bytes,
        "private_key_hex": priv_bytes.hex(),
        "public_key_bytes": sol["public_key_bytes"],
        "public_key_hex": sol["public_key_hex"],
        "public_key_display_label": "公開鍵 (32-byte, hex)",
        "public_key_display_hex": sol["public_key_hex"],
        "chain_code_bytes": chain_code,
        "chain_code_hex": chain_code.hex(),
    }


def derive_path_steps_secp(seed_bytes: bytes, path: str) -> List[Dict[str, Any]]:
    segments = parse_bip32_path(path)
    priv_bytes, chain_code = _master_key_secp256k1(seed_bytes)

    steps: List[Dict[str, Any]] = [
        _ctx_to_step_data_secp(priv_bytes, chain_code, 0, "m", "master", "m")
    ]

    current_path = "m"
    depth = 0

    for seg in segments:
        idx = seg["index"] + (0x80000000 if seg["hardened"] else 0)
        suffix = "'" if seg["hardened"] else ""
        current_path = f"{current_path}/{seg['index']}{suffix}"
        priv_bytes, chain_code = _ckd_priv_secp256k1(priv_bytes, chain_code, idx)
        depth += 1
        steps.append(
            _ctx_to_step_data_secp(
                priv_bytes,
                chain_code,
                depth,
                current_path,
                seg["label"],
                f"{seg['index']}{suffix}",
            )
        )

    return steps


def derive_path_steps_ed25519(seed_bytes: bytes, path: str) -> List[Dict[str, Any]]:
    validate_ed25519_path(path)
    segments = parse_bip32_path(path)
    priv_bytes, chain_code = _master_key_ed25519(seed_bytes)

    steps: List[Dict[str, Any]] = [
        _ctx_to_step_data_ed25519(priv_bytes, chain_code, 0, "m", "master", "m")
    ]

    current_path = "m"
    depth = 0

    for seg in segments:
        idx = seg["index"] + 0x80000000
        suffix = "'"
        current_path = f"{current_path}/{seg['index']}{suffix}"
        priv_bytes, chain_code = _ckd_priv_ed25519(priv_bytes, chain_code, idx)
        depth += 1
        steps.append(
            _ctx_to_step_data_ed25519(
                priv_bytes,
                chain_code,
                depth,
                current_path,
                seg["label"],
                f"{seg['index']}{suffix}",
            )
        )

    return steps


def _build_chain_package(chain_name: str, path: str, seed_bytes: bytes) -> Dict[str, Any]:
    if chain_name in ("EVM", "TRON"):
        steps = derive_path_steps_secp(seed_bytes, path)
        final_step = steps[-1]
        final_pub_uncompressed = final_step["public_key_uncompressed_bytes"]

        if chain_name == "EVM":
            address_data = evm_address_from_uncompressed_pub(final_pub_uncompressed)
            address = address_data["address_checksum"]
            address_detail = address_data
        else:
            address_data = tron_address_from_uncompressed_pub(final_pub_uncompressed)
            address = address_data["address_base58"]
            address_detail = address_data

        return {
            "chain_name": chain_name,
            "curve": CHAIN_DEFAULTS[chain_name]["curve"],
            "curve_badge": CHAIN_DEFAULTS[chain_name]["curve_badge"],
            "path": path,
            "steps": steps,
            "final_private_key_hex": final_step["private_key_hex"],
            "final_public_key_hex": final_step["public_key_display_hex"],
            "address": address,
            "address_detail": address_detail,
        }

    if chain_name == "Solana":
        steps = derive_path_steps_ed25519(seed_bytes, path)
        final_step = steps[-1]
        sol = solana_pubkey_and_address_from_private_key(final_step["private_key_bytes"])
        return {
            "chain_name": chain_name,
            "curve": CHAIN_DEFAULTS[chain_name]["curve"],
            "curve_badge": CHAIN_DEFAULTS[chain_name]["curve_badge"],
            "path": path,
            "steps": steps,
            "final_private_key_hex": final_step["private_key_hex"],
            "final_public_key_hex": sol["public_key_hex"],
            "address": sol["address_base58"],
            "address_detail": sol,
        }

    raise ValueError(f"Unsupported chain: {chain_name}")


def derive_evm_account_series(
    mnemonic: str,
    passphrase: str,
    base_path: str,
    indices: List[int],
) -> List[Dict[str, Any]]:
    seed = get_seed_analysis(mnemonic, passphrase)["seed_bytes"]
    packages = []

    for idx in indices:
        full_path = f"{base_path}/{idx}"
        pkg = _build_chain_package("EVM", full_path, seed)
        pkg["account_index"] = idx
        packages.append(pkg)

    return packages


def derive_all_chains(
    mnemonic: str,
    passphrase: str,
    chain_paths: Dict[str, str],
) -> List[Dict[str, Any]]:
    seed = get_seed_analysis(mnemonic, passphrase)["seed_bytes"]
    results = []

    for chain_name, path in chain_paths.items():
        results.append(_build_chain_package(chain_name, path, seed))

    return results