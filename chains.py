import hashlib
from typing import Any, Dict, List

import base58
from Crypto.Hash import keccak
from eth_utils import to_checksum_address
from nacl.signing import SigningKey

try:
    from bip_utils import Bip32Ed25519Slip
except ImportError:
    from bip_utils import Bip32Slip10Ed25519 as Bip32Ed25519Slip

from bip_utils import Bip32Secp256k1, Bip32Utils

from utils import CHAIN_DEFAULTS, get_seed_analysis, parse_bip32_path


def _keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def _double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _ensure_uncompressed_secp_pub(pub_bytes: bytes) -> bytes:
    if len(pub_bytes) == 65 and pub_bytes[0] == 0x04:
        return pub_bytes
    raise ValueError("Expected a 65-byte uncompressed secp256k1 public key starting with 0x04.")


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
    signing_key = SigningKey(priv_key_bytes)
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


def _ctx_to_step_data_secp(ctx: Any, path_so_far: str, label: str, index_repr: str) -> Dict[str, Any]:
    priv_bytes = bytes(ctx.PrivateKey().Raw().ToBytes())
    pub_uncompressed = bytes(ctx.PublicKey().RawUncompressed().ToBytes())
    pub_compressed = bytes(ctx.PublicKey().RawCompressed().ToBytes())
    chain_code = bytes(ctx.ChainCode().ToBytes())

    return {
        "path": path_so_far,
        "label": label,
        "index_repr": index_repr,
        "depth": int(ctx.Depth().ToInt()),
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
    }


def _ctx_to_step_data_ed25519(ctx: Any, path_so_far: str, label: str, index_repr: str) -> Dict[str, Any]:
    priv_bytes = bytes(ctx.PrivateKey().Raw().ToBytes())
    chain_code = bytes(ctx.ChainCode().ToBytes())
    sol = solana_pubkey_and_address_from_private_key(priv_bytes)

    return {
        "path": path_so_far,
        "label": label,
        "index_repr": index_repr,
        "depth": int(ctx.Depth().ToInt()),
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
    ctx = Bip32Secp256k1.FromSeed(seed_bytes)

    steps: List[Dict[str, Any]] = [
        _ctx_to_step_data_secp(ctx, "m", "master", "m")
    ]

    current_path = "m"
    for seg in segments:
        idx = Bip32Utils.HardenIndex(seg["index"]) if seg["hardened"] else seg["index"]
        suffix = "'" if seg["hardened"] else ""
        current_path = f"{current_path}/{seg['index']}{suffix}"
        ctx = ctx.ChildKey(idx)
        steps.append(
            _ctx_to_step_data_secp(
                ctx,
                current_path,
                seg["label"],
                f"{seg['index']}{suffix}",
            )
        )

    return steps


def derive_path_steps_ed25519(seed_bytes: bytes, path: str) -> List[Dict[str, Any]]:
    validate_ed25519_path(path)
    segments = parse_bip32_path(path)
    ctx = Bip32Ed25519Slip.FromSeed(seed_bytes)

    steps: List[Dict[str, Any]] = [
        _ctx_to_step_data_ed25519(ctx, "m", "master", "m")
    ]

    current_path = "m"
    for seg in segments:
        idx = Bip32Utils.HardenIndex(seg["index"])
        suffix = "'"
        current_path = f"{current_path}/{seg['index']}{suffix}"
        ctx = ctx.ChildKey(idx)
        steps.append(
            _ctx_to_step_data_ed25519(
                ctx,
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
    seed_analysis = get_seed_analysis(mnemonic, passphrase)
    seed_bytes = seed_analysis["seed_bytes"]

    accounts: List[Dict[str, Any]] = []
    for idx in indices:
        full_path = f"{base_path}/{idx}"
        steps = derive_path_steps_secp(seed_bytes, full_path)
        final_step = steps[-1]
        address_data = evm_address_from_uncompressed_pub(final_step["public_key_bytes"])

        accounts.append(
            {
                "index": idx,
                "path": full_path,
                "private_key_hex": final_step["private_key_hex"],
                "public_key_hex": final_step["public_key_display_hex"],
                "address": address_data["address_checksum"],
                "steps": steps,
            }
        )

    return accounts


def derive_all_chains(
    mnemonic: str,
    passphrase: str,
    evm_path: str,
    tron_path: str,
    solana_path: str,
) -> Dict[str, Any]:
    seed_analysis = get_seed_analysis(mnemonic, passphrase)
    seed_bytes = seed_analysis["seed_bytes"]

    chains = {
        "EVM": _build_chain_package("EVM", evm_path, seed_bytes),
        "TRON": _build_chain_package("TRON", tron_path, seed_bytes),
        "Solana": _build_chain_package("Solana", solana_path, seed_bytes),
    }

    return {
        "mnemonic": mnemonic,
        "passphrase": passphrase,
        "seed_hex": seed_analysis["seed_hex"],
        "seed_bytes": seed_bytes,
        "chains": chains,
    }