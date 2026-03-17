import hashlib
import html
import re
import unicodedata
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from mnemonic import Mnemonic

APP_TITLE = "HDウォレット学習アプリ"
APP_DESCRIPTION = (
    "同じ固定ダミー mnemonic から、EVM・TRON・Solana のアドレスや "
    "MetaMask の複数アカウントがどのように分岐して生成されるかを、日本語で学ぶための教育用 Streamlit アプリです。"
)

SECURITY_NOTICE = """
**実在のシードフレーズは絶対に入力しないでください。**  
このアプリは教育目的であり、固定のダミー mnemonic だけを表示します。
"""

EXPLANATION_TEXT = """
このアプリは、**HDウォレットの D（Deterministic）と H（Hierarchical）を学ぶ**ことを目的にしています。  
前半では、同じ入力と同じルールから同じ結果が再現されることを見ます。  
後半では、1つの seed から複数の枝が伸び、複数のアドレスが作られることを見ます。
"""

DUMMY_MNEMONIC = "valley lava own option spy once lunch often net stool sudden vocal"
DUMMY_PASSPHRASE = ""

CHAIN_DEFAULTS = {
    "EVM": {
        "path": "m/44'/60'/0'/0/0",
        "curve": "secp256k1",
        "curve_badge": "badge-secp",
    },
    "TRON": {
        "path": "m/44'/195'/0'/0/0",
        "curve": "secp256k1",
        "curve_badge": "badge-secp",
    },
    "Solana": {
        "path": "m/44'/501'/0'/0'",
        "curve": "ed25519",
        "curve_badge": "badge-ed",
    },
    "MetaMask": {
        "base_path": "m/44'/60'/0'/0",
    },
}


def inject_custom_css() -> None:
    st.markdown(
        """
<style>
.block-container {
    padding-top: 1.3rem;
    padding-bottom: 2rem;
    max-width: 1320px;
}
.hero-card,
.summary-card,
.mini-card,
.flow-box,
.inner-box {
    background: #ffffff;
    border: 1px solid #e6def5;
    border-radius: 18px;
    padding: 1rem 1rem;
    box-shadow: 0 8px 24px rgba(111, 87, 180, 0.06);
    margin-bottom: 0.9rem;
}
.hero-card {
    background: linear-gradient(180deg, #fcfbff 0%, #f6f2ff 100%);
    border: 1px solid #ddd1f7;
}
.hero-title,
.inner-title {
    font-weight: 800;
    color: #4d3f77;
    margin-bottom: 0.35rem;
}
.hero-text {
    font-size: 1.05rem;
    font-weight: 700;
    line-height: 1.6;
}
.flow-box {
    background: linear-gradient(180deg, #fcfbff 0%, #f8f5ff 100%);
}
.flow-step {
    border: 1px solid #d9d1ef;
    border-radius: 14px;
    padding: 0.95rem;
    text-align: center;
    font-weight: 700;
    background: #fff;
}
.flow-arrow {
    text-align: center;
    font-size: 1.15rem;
    color: #6d5ca5;
    padding: 0.25rem 0;
}
.split {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
}
.two-box {
    display: grid;
    grid-template-columns: 3fr 1fr;
    gap: 0.8rem;
}
.mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.wrap {
    word-break: break-all;
    overflow-wrap: anywhere;
    line-height: 1.65;
}
.tiny {
    font-size: 0.86rem;
    color: #615c70;
}
.section-title {
    font-size: 1.35rem;
    font-weight: 800;
    color: #403256;
    margin-top: 0.35rem;
    margin-bottom: 0.2rem;
}
.section-subtitle {
    color: #6d687d;
    margin-bottom: 1rem;
}
.notice-box {
    padding: 0.95rem 1rem;
    border-radius: 16px;
    margin-bottom: 1rem;
    border: 1px solid #eadcf7;
}
.notice-danger {
    background: #fff7fb;
    border-color: #f0cad8;
}
.notice-info {
    background: #f7fbff;
    border-color: #d8e9fb;
}
.badge {
    display: inline-block;
    border-radius: 999px;
    padding: 0.14rem 0.58rem;
    font-size: 0.75rem;
    font-weight: 700;
    margin-left: 0.35rem;
}
.badge-secp {
    background: #efe9ff;
    color: #5f46b5;
}
.badge-ed {
    background: #e8f8ef;
    color: #177245;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_notice_box(text: str, kind: str = "info") -> None:
    klass = "notice-danger" if kind == "danger" else "notice-info"
    st.markdown(
        f'<div class="notice-box {klass}">{text}</div>',
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
<div class="section-title">{html.escape(title)}</div>
<div class="section-subtitle">{html.escape(subtitle)}</div>
""",
        unsafe_allow_html=True,
    )


def render_badge(text: str, css_class: str) -> str:
    return f'<span class="badge {css_class}">{html.escape(text)}</span>'


def safe_exception_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)}"


def mask_middle(text: str, left: int = 10, right: int = 10) -> str:
    if len(text) <= left + right + 3:
        return text
    return text[:left] + " ... " + text[-right:]


def bits_to_grouped_string(bit_str: str, group_size: int = 8) -> str:
    return " ".join(bit_str[i:i + group_size] for i in range(0, len(bit_str), group_size))


def validate_mnemonic(mnemonic: str) -> None:
    mnemo = Mnemonic("english")
    if not mnemo.check(mnemonic):
        raise ValueError("The mnemonic is not a valid BIP-39 English mnemonic.")


def get_mnemonic_analysis(mnemonic: str) -> Dict[str, Any]:
    validate_mnemonic(mnemonic)
    mnemo = Mnemonic("english")
    words = mnemonic.split()

    if len(words) != 12:
        raise ValueError("This app currently expects a 12-word mnemonic.")

    indexed = []
    all_bits = ""

    for idx, word in enumerate(words):
        word_index = mnemo.wordlist.index(word)
        bits11 = format(word_index, "011b")
        all_bits += bits11
        indexed.append(
            {
                "position": idx + 1,
                "word": word,
                "word_index": word_index,
                "bits11": bits11,
            }
        )

    entropy_bit_length = 128
    checksum_bit_length = 4

    entropy_bits = all_bits[:entropy_bit_length]
    checksum_bits = all_bits[entropy_bit_length:]
    entropy_bytes = int(entropy_bits, 2).to_bytes(entropy_bit_length // 8, "big")
    sha256_first_byte_bits = format(hashlib.sha256(entropy_bytes).digest()[0], "08b")
    computed_checksum_bits = sha256_first_byte_bits[:checksum_bit_length]

    return {
        "words": words,
        "indexed_words": indexed,
        "all_bits": all_bits,
        "entropy_bits": entropy_bits,
        "checksum_bits": checksum_bits,
        "computed_checksum_bits": computed_checksum_bits,
        "checksum_matches": checksum_bits == computed_checksum_bits,
        "entropy_bytes": entropy_bytes,
        "entropy_hex": entropy_bytes.hex(),
        "entropy_bit_length": entropy_bit_length,
        "checksum_bit_length": checksum_bit_length,
    }


def get_seed_analysis(mnemonic: str, passphrase: str) -> Dict[str, Any]:
    validate_mnemonic(mnemonic)

    mnemonic_nfkd = unicodedata.normalize("NFKD", mnemonic)
    passphrase_nfkd = unicodedata.normalize("NFKD", passphrase)
    salt_str = "mnemonic" + passphrase_nfkd

    seed_bytes = hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic_nfkd.encode("utf-8"),
        salt_str.encode("utf-8"),
        2048,
        dklen=64,
    )
    return {
        "salt_str": salt_str,
        "iterations": 2048,
        "dklen": 64,
        "normalization": "UTF-8 NFKD",
        "mnemonic_nfkd": mnemonic_nfkd,
        "passphrase_nfkd": passphrase_nfkd,
        "seed_bytes": seed_bytes,
        "seed_hex": seed_bytes.hex(),
    }


def parse_bip32_path(path: str) -> List[Dict[str, Any]]:
    if not path or not isinstance(path, str):
        raise ValueError("Path must be a non-empty string.")

    norm = path.strip()
    if not norm.startswith("m"):
        raise ValueError("Path must start with 'm'.")

    if norm == "m":
        return []

    parts = norm.split("/")
    if parts[0] != "m":
        raise ValueError("Path must start with 'm/'.")

    parsed: List[Dict[str, Any]] = []
    label_map = {
        1: "purpose",
        2: "coin_type",
        3: "account",
        4: "change",
        5: "address_index",
    }

    for depth, raw_part in enumerate(parts[1:], start=1):
        if not raw_part:
            raise ValueError(f"Empty path segment at depth {depth}.")

        hardened = raw_part.endswith("'")
        core = raw_part[:-1] if hardened else raw_part

        if not re.fullmatch(r"\d+", core):
            raise ValueError(f"Invalid path segment: {raw_part}")

        index = int(core)
        if index < 0:
            raise ValueError("Path index cannot be negative.")

        parsed.append(
            {
                "depth": depth,
                "label": label_map.get(depth, f"level_{depth}"),
                "index": index,
                "hardened": hardened,
            }
        )

    return parsed


def build_step_rows(mnemonic_analysis: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in mnemonic_analysis["indexed_words"]:
        rows.append(
            {
                "番号": item["position"],
                "単語": item["word"],
                "BIP-39 index": item["word_index"],
                "11-bit 表現": item["bits11"],
            }
        )
    return pd.DataFrame(rows)


def build_derivation_summary_rows(chain: Dict[str, Any], secret_visibility: str = "Masked") -> pd.DataFrame:
    rows = []
    for step in chain["steps"]:
        rows.append(
            {
                "深さ": step["depth"],
                "ラベル": step["label"],
                "index": step["index_repr"],
                "path": step["path"],
                "秘密鍵": step["private_key_hex"] if secret_visibility == "Full" else mask_middle(step["private_key_hex"], 14, 14),
                "chain code": step["chain_code_hex"] if secret_visibility == "Full" else mask_middle(step["chain_code_hex"], 14, 14),
            }
        )
    return pd.DataFrame(rows)


def build_key_material_rows(chain: Dict[str, Any], secret_visibility: str = "Masked") -> pd.DataFrame:
    rows = []
    for step in chain["steps"]:
        rows.append(
            {
                "path": step["path"],
                "秘密鍵 (hex)": step["private_key_hex"] if secret_visibility == "Full" else mask_middle(step["private_key_hex"], 18, 18),
                step.get("public_key_display_label", "公開鍵 (hex)"): step["public_key_display_hex"] if secret_visibility == "Full" else mask_middle(step["public_key_display_hex"], 18, 18),
                "chain code (hex)": step["chain_code_hex"] if secret_visibility == "Full" else mask_middle(step["chain_code_hex"], 18, 18),
            }
        )
    return pd.DataFrame(rows)


def build_compare_rows(chains: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for chain_name, chain in chains.items():
        rows.append(
            {
                "チェーン": chain_name,
                "鍵生成に使う曲線": chain["curve"],
                "導出パス": chain["path"],
                "最終アドレス": chain["address"],
                "アドレス形式": (
                    "0x + EIP-55"
                    if chain_name == "EVM"
                    else "Base58Check (T...)"
                    if chain_name == "TRON"
                    else "Base58（32-byte 公開鍵）"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_path_component_rows(path: str) -> pd.DataFrame:
    meaning_map = {
        "purpose": "規格の種類",
        "coin_type": "チェーンの種類",
        "account": "口座・用途のまとまり",
        "change": "受取 / おつり等の区別",
        "address_index": "アドレス番号",
    }

    parsed = parse_bip32_path(path)
    rows = [{"階層": "m", "意味": "ルート", "値": "m", "hardened": "-"}]

    for item in parsed:
        suffix = "'" if item["hardened"] else ""
        rows.append(
            {
                "階層": item["label"],
                "意味": meaning_map.get(item["label"], item["label"]),
                "値": f'{item["index"]}{suffix}',
                "hardened": "Yes" if item["hardened"] else "No",
            }
        )

    return pd.DataFrame(rows)


def build_metamask_index_rows(accounts: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for account in accounts:
        rows.append(
            {
                "index": account["index"],
                "full path": account["path"],
                "address": account["address"],
                "public key": mask_middle(account["public_key_hex"], 18, 18),
            }
        )
    return pd.DataFrame(rows)