import inspect
from typing import Any, Dict, List

import streamlit as st

from chains import derive_all_chains, derive_evm_account_series
from utils import (
    APP_DESCRIPTION,
    APP_TITLE,
    CHAIN_DEFAULTS,
    DUMMY_MNEMONIC,
    DUMMY_PASSPHRASE,
    EXPLANATION_TEXT,
    SECURITY_NOTICE,
    bits_to_grouped_string,
    build_compare_rows,
    build_derivation_summary_rows,
    build_key_material_rows,
    build_metamask_index_rows,
    build_path_component_rows,
    build_step_rows,
    get_mnemonic_analysis,
    get_seed_analysis,
    inject_custom_css,
    mask_middle,
    render_badge,
    render_notice_box,
    render_section_header,
    safe_exception_text,
)


def format_u32_hex(value: int) -> str:
    return int(value).to_bytes(4, "big").hex()


def format_u32_bits(value: int) -> str:
    bits = f"{int(value):032b}"
    return " ".join(bits[i:i + 8] for i in range(0, 32, 8))


def normalize_derivation_result(
    raw_result: Any,
    mnemonic: str,
    passphrase: str,
    seed_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    derive_all_chains の返り値が
    - 新版: List[Dict[str, Any]]
    - 旧版: {"mnemonic": ..., "passphrase": ..., "seed_hex": ..., "chains": {...}}
    のどちらでも吸収して app.py 内部の共通形式にそろえる。
    """
    if isinstance(raw_result, dict) and "chains" in raw_result:
        chains = raw_result["chains"]
        if not isinstance(chains, dict):
            raise ValueError("derive_all_chains returned dict, but 'chains' is not a dict.")
        return {
            "mnemonic": raw_result.get("mnemonic", mnemonic),
            "passphrase": raw_result.get("passphrase", passphrase),
            "seed_hex": raw_result.get("seed_hex", seed_analysis["seed_hex"]),
            "seed_bytes": raw_result.get("seed_bytes", seed_analysis["seed_bytes"]),
            "chains": chains,
        }

    if isinstance(raw_result, list):
        chains_dict: Dict[str, Dict[str, Any]] = {}
        for pkg in raw_result:
            if not isinstance(pkg, dict):
                raise ValueError("derive_all_chains returned list containing a non-dict element.")
            chain_name = pkg.get("chain_name")
            if not chain_name:
                raise ValueError("Each chain package must include 'chain_name'.")
            chains_dict[chain_name] = pkg

        return {
            "mnemonic": mnemonic,
            "passphrase": passphrase,
            "seed_hex": seed_analysis["seed_hex"],
            "seed_bytes": seed_analysis["seed_bytes"],
            "chains": chains_dict,
        }

    raise ValueError("Unsupported derive_all_chains return format.")


def call_derive_all_chains_compat(
    mnemonic: str,
    passphrase: str,
    evm_path: str,
    tron_path: str,
    solana_path: str,
) -> Any:
    """
    chains.py の新旧シグネチャ差分を吸収する。
    新版:
      derive_all_chains(mnemonic, passphrase, chain_paths={...})
    旧版:
      derive_all_chains(mnemonic, passphrase, evm_path=..., tron_path=..., solana_path=...)
    """
    try:
        sig = inspect.signature(derive_all_chains)
        params = sig.parameters
    except Exception:
        params = {}

    if "chain_paths" in params:
        return derive_all_chains(
            mnemonic=mnemonic,
            passphrase=passphrase,
            chain_paths={
                "EVM": evm_path,
                "TRON": tron_path,
                "Solana": solana_path,
            },
        )

    return derive_all_chains(
        mnemonic=mnemonic,
        passphrase=passphrase,
        evm_path=evm_path,
        tron_path=tron_path,
        solana_path=solana_path,
    )


def normalize_account(account: Dict[str, Any]) -> Dict[str, Any]:
    idx = account.get("index", account.get("account_index"))
    pub_hex = account.get("public_key_hex", account.get("final_public_key_hex", ""))
    priv_hex = account.get("private_key_hex", account.get("final_private_key_hex", ""))

    normalized = dict(account)
    normalized["index"] = idx
    normalized["public_key_hex"] = pub_hex
    normalized["private_key_hex"] = priv_hex
    return normalized


def get_public_key_label(step: Dict[str, Any]) -> str:
    return step.get("public_key_display_label", "公開鍵")


def get_public_key_hex(step: Dict[str, Any]) -> str:
    if "public_key_display_hex" in step:
        return step["public_key_display_hex"]
    if "public_key_uncompressed_hex" in step:
        return step["public_key_uncompressed_hex"]
    return step.get("public_key_hex", "")


st.set_page_config(
    page_title="HDウォレット学習アプリ",
    page_icon="🔐",
    layout="wide",
)

inject_custom_css()

mnemonic = DUMMY_MNEMONIC
passphrase = DUMMY_PASSPHRASE
evm_path = CHAIN_DEFAULTS["EVM"]["path"]
tron_path = CHAIN_DEFAULTS["TRON"]["path"]
solana_path = CHAIN_DEFAULTS["Solana"]["path"]
metamask_base_path = CHAIN_DEFAULTS["MetaMask"]["base_path"]

try:
    mnemonic_analysis = get_mnemonic_analysis(mnemonic)
    seed_analysis = get_seed_analysis(mnemonic, passphrase)

    raw_derivation_result = call_derive_all_chains_compat(
        mnemonic=mnemonic,
        passphrase=passphrase,
        evm_path=evm_path,
        tron_path=tron_path,
        solana_path=solana_path,
    )
    derivation_result = normalize_derivation_result(
        raw_result=raw_derivation_result,
        mnemonic=mnemonic,
        passphrase=passphrase,
        seed_analysis=seed_analysis,
    )

    metamask_accounts_raw = derive_evm_account_series(
        mnemonic=mnemonic,
        passphrase=passphrase,
        base_path=metamask_base_path,
        indices=[0, 1, 2],
    )
    metamask_accounts = [normalize_account(a) for a in metamask_accounts_raw]
except Exception as exc:
    st.error("計算中にエラーが発生しました。")
    st.code(safe_exception_text(exc))
    st.stop()

account0 = metamask_accounts[0]
account1 = metamask_accounts[1]

st.title(APP_TITLE)
st.caption(APP_DESCRIPTION)

render_notice_box(SECURITY_NOTICE, kind="danger")

ctrl_col1, ctrl_col2 = st.columns([1, 1])
with ctrl_col1:
    show_bit_view = st.checkbox("ニーモニックのビット構造も表示する", value=False)
with ctrl_col2:
    show_key_details = st.checkbox("詳細テーブルも表示する", value=False)

top_col1, top_col2, top_col3, top_col4 = st.columns(4)
top_col1.metric("単語数", len(mnemonic_analysis["words"]))
top_col2.metric("エントロピー", f'{mnemonic_analysis["entropy_bit_length"]} bit')
top_col3.metric("seed", f'{len(seed_analysis["seed_bytes"])} byte')
top_col4.metric("比較チェーン数", len(derivation_result["chains"]))

st.markdown(
    f"""
<div class="hero-card">
    <div class="hero-title">固定ダミー mnemonic</div>
    <div class="mono hero-text">{mnemonic}</div>
    <div class="tiny" style="margin-top:0.65rem;">
        実在のシードフレーズは扱わず、教育目的の固定ダミー mnemonic のみを表示しています。
    </div>
</div>
""",
    unsafe_allow_html=True,
)

intro_tab, deterministic_tab, compare_tab, hierarchical_tab, metamask_tab = st.tabs(
    ["はじめに", "D：決定論", "チェーン比較", "H：階層構造", "MetaMask の複数アカウント"]
)

with intro_tab:
    render_section_header(
        "このアプリの立て付け",
        "このアプリは、シードフレーズからアドレスが生まれる流れを通じて、HDウォレットの仕組みを学ぶためのものです。",
    )

    st.markdown(
        """
このアプリでは、**HDウォレット**の **D（Deterministic）** と **H（Hierarchical）** を、
別々のタブで順番に学べるようにしています。

- **「D：決定論」タブから「チェーン比較」タブまでは D を中心に示しています。**
- **「H：階層構造」タブと「MetaMask の複数アカウント」タブでは H を中心に示しています。**

ここでいう **HDウォレット** とは、**Hierarchical Deterministic Wallet** のことです。
"""
    )

    left_a, left_b = st.columns(2)
    with left_a:
        st.markdown(
            """
<div class="mini-card">
    <div class="inner-title">D = Deterministic（決定論的）</div>
    <div>
        同じシードフレーズと同じルールを使えば、いつでも同じ鍵と同じアドレスを再現できます。<br>
        つまり、結果が偶然ではなく、入力によって決まるということです。
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with left_b:
        st.markdown(
            """
<div class="mini-card">
    <div class="inner-title">H = Hierarchical（階層的）</div>
    <div>
        1つの seed から、用途や番号ごとに複数の子鍵・複数のアドレスを順番に作れます。
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### このアプリが見せたいこと")
    st.markdown(EXPLANATION_TEXT)

    intro_left, intro_right = st.columns([1.05, 1.0])

    with intro_left:
        st.markdown(
            """
<div class="flow-box">
    <div class="flow-step">12語のニーモニック</div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step">BIP-39 に基づく共通の seed</div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step split">
        <div>D：同じ入力なら同じ結果</div>
        <div>H：1つの seed から枝分かれ</div>
        <div>両方をまとめて HD</div>
    </div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step">チェーン別アドレス / 複数アカウント</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with intro_right:
        st.markdown("### ここで見る順番")
        st.markdown(
            """
1. **D：決定論**  
   まず、同じニーモニックから同じ seed ができ、同じルールを使えば同じアドレスが再現されることを見ます。

2. **チェーン比較**  
   次に、共通の出発点から EVM・TRON・Solana がどのように分岐するかを見ます。

3. **H：階層構造**  
   その後で、導出パスがどのように階層を作っているかを見ます。

4. **MetaMask の複数アカウント**  
   最後に、同じ seed から index を 0 / 1 / 2 と変えるだけで複数アドレスが作れる様子を見ます。
"""
        )

    st.markdown("### 固定ダミー mnemonic と seed")
    fixed_col1, fixed_col2 = st.columns(2)

    with fixed_col1:
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">固定ダミー mnemonic</div>
    <div class="mono wrap">{mnemonic}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with fixed_col2:
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">共通の seed（抜粋表示）</div>
    <div class="mono wrap">{mask_middle(seed_analysis["seed_hex"], left=28, right=28)}</div>
</div>
""",
            unsafe_allow_html=True,
        )

with deterministic_tab:
    render_section_header(
        "D：決定論",
        "同じニーモニックと同じルールから、いつでも同じ seed と同じアドレスが再現されます。",
    )

    st.markdown(
        """
ここで見たいポイントは、**結果が偶然ではなく、入力と手順によって決まる**ということです。  
同じ 12語のニーモニックからは、BIP-39 に基づいて同じ seed が作られます。  
そして、その同じ seed と同じ導出パスを使えば、同じ鍵・同じアドレスが再現されます。
"""
    )

    st.markdown("### 12語のニーモニックを 11-bit ずつ見る")
    st.dataframe(
        build_step_rows(mnemonic_analysis),
        use_container_width=True,
        hide_index=True,
    )

    if show_bit_view:
        st.markdown("### 132 bit 全体の構造")
        st.markdown(
            f"""
<div class="summary-card">
    <div class="tiny">132 bit 全体</div>
    <div class="mono wrap">{bits_to_grouped_string(mnemonic_analysis["all_bits"], 11)}</div>
    <div class="tiny" style="margin-top:0.8rem;">Entropy 128 bit</div>
    <div class="mono wrap">{bits_to_grouped_string(mnemonic_analysis["entropy_bits"], 8)}</div>
    <div class="tiny" style="margin-top:0.8rem;">Checksum 4 bit</div>
    <div class="mono wrap">{mnemonic_analysis["checksum_bits"]}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    det_col1, det_col2 = st.columns(2)

    with det_col1:
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">Entropy</div>
    <div class="mono wrap">{mnemonic_analysis["entropy_hex"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">{mnemonic_analysis["entropy_bit_length"]} bit</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with det_col2:
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">Checksum の確認</div>
    <div class="tiny">ニーモニックに埋め込まれた checksum</div>
    <div class="mono wrap">{mnemonic_analysis["checksum_bits"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">entropy から再計算した checksum</div>
    <div class="mono wrap">{mnemonic_analysis["computed_checksum_bits"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">一致判定</div>
    <div class="mono wrap">{'一致' if mnemonic_analysis["checksum_matches"] else '不一致'}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### BIP-39 に基づく seed")
    st.dataframe(
        [
            {
                "項目": "PBKDF2",
                "値": "HMAC-SHA512",
            },
            {
                "項目": "反復回数",
                "値": str(seed_analysis["iterations"]),
            },
            {
                "項目": "dkLen",
                "値": str(seed_analysis["dklen"]),
            },
            {
                "項目": "salt",
                "値": seed_analysis["salt_str"],
            },
            {
                "項目": "seed (hex)",
                "値": seed_analysis["seed_hex"],
            },
        ],
        use_container_width=True,
        hide_index=True,
    )

with compare_tab:
    render_section_header(
        "チェーン比較",
        "同じ seed から出発しても、導出パス・曲線・アドレス化ルールが違えば、出てくるアドレスは変わります。",
    )

    st.markdown(
        """
ここで重要なのは、**出発点の seed は共通**でも、各チェーンでは

- **導出パス**
- **鍵生成に使う曲線**
- **公開鍵からアドレスへ変換するルール**

が異なる、ということです。
"""
    )

    chain_cards = st.columns(3)
    for idx, chain_name in enumerate(["EVM", "TRON", "Solana"]):
        chain = derivation_result["chains"][chain_name]
        with chain_cards[idx]:
            badge_html = render_badge(chain["curve"], CHAIN_DEFAULTS[chain_name]["curve_badge"])
            st.markdown(
                f"""
<div class="summary-card">
    <div class="inner-title">{chain_name} {badge_html}</div>
    <div class="tiny">Path</div>
    <div class="mono wrap">{chain["path"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">Address</div>
    <div class="mono wrap">{chain["address"]}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("### 比較表")
    st.dataframe(
        build_compare_rows(derivation_result["chains"]),
        use_container_width=True,
        hide_index=True,
    )

    for chain_name in ["EVM", "TRON", "Solana"]:
        chain = derivation_result["chains"][chain_name]
        st.markdown(f"## {chain_name}")
        st.dataframe(
            build_derivation_summary_rows(chain),
            use_container_width=True,
            hide_index=True,
        )

        if show_key_details:
            st.dataframe(
                build_key_material_rows(chain),
                use_container_width=True,
                hide_index=True,
            )

with hierarchical_tab:
    render_section_header(
        "H：階層構造",
        "導出パスは 1 本の文字列ではなく、親から子へ順にたどっていく階層の指定です。",
    )

    st.markdown(
        """
たとえば EVM の既定 path `m/44'/60'/0'/0/0` は、
1回でまとめて計算される魔法の文字列ではなく、
**master → purpose → coin_type → account → change → address_index**
という順番で、枝をたどっていく指定です。
"""
    )

    hierarchy_cols = st.columns(3)
    for idx, chain_name in enumerate(["EVM", "TRON", "Solana"]):
        chain = derivation_result["chains"][chain_name]
        with hierarchy_cols[idx]:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="inner-title">{chain_name}</div>
    <div class="mono wrap">{chain["path"]}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            st.dataframe(
                build_path_component_rows(chain["path"]),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("## EVM path を順に追う")
    evm_chain = derivation_result["chains"]["EVM"]
    st.dataframe(
        build_derivation_summary_rows(evm_chain),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 最終ステップの鍵素材")
    evm_final = evm_chain["steps"][-1]
    final_rows = [
        {
            "項目": "Path",
            "値": evm_final["path"],
        },
        {
            "項目": "秘密鍵 (hex)",
            "値": evm_final["private_key_hex"],
        },
        {
            "項目": get_public_key_label(evm_final),
            "値": get_public_key_hex(evm_final),
        },
        {
            "項目": "Chain code (hex)",
            "値": evm_final["chain_code_hex"],
        },
        {
            "項目": "Address",
            "値": evm_chain["address"],
        },
    ]
    st.dataframe(final_rows, use_container_width=True, hide_index=True)

with metamask_tab:
    render_section_header(
        "MetaMask の複数アカウント",
        "同じ seed でも、最後の address index を変えるだけで、別々のアドレスが順番に作られます。",
    )

    st.markdown(
        """
MetaMask が Secret Recovery Phrase を既定 import する文脈では、  
EVM 用の base path として `m/44'/60'/0'/0` が使われ、その先の **address index** を  
`0`, `1`, `2` と変えることで、別々のアドレスを順番に導出できます。
"""
    )

    st.markdown(
        f"""
<div class="summary-card">
    <div class="inner-title">今回固定した base path</div>
    <div class="mono wrap">{metamask_base_path}</div>
    <div class="tiny" style="margin-top:0.75rem;">
        この base path の末尾に <span class="mono">/0</span>, <span class="mono">/1</span>, <span class="mono">/2</span> を付けて比較します。
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.dataframe(
        build_metamask_index_rows(metamask_accounts),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("## /0 と /1 で、実際にどの文字列が変わるか")
    st.markdown(
        """
`m/44'/60'/0'/0/0` と `m/44'/60'/0'/0/1` の違いは、最後の **address index** が `0` か `1` かだけです。  
しかし、その数値自体が子鍵生成の計算入力に入るため、子秘密鍵・公開鍵・アドレスは、実際の英数字の並びとして大きく変わります。
"""
    )

    st.dataframe(
        [
            {
                "項目": "Full path",
                "index = 0": account0["path"],
                "index = 1": account1["path"],
            },
            {
                "項目": "address index（10進）",
                "index = 0": str(account0["index"]),
                "index = 1": str(account1["index"]),
            },
            {
                "項目": "address index（32bit hex）",
                "index = 0": format_u32_hex(account0["index"]),
                "index = 1": format_u32_hex(account1["index"]),
            },
            {
                "項目": "address index（32bit bit列）",
                "index = 0": format_u32_bits(account0["index"]),
                "index = 1": format_u32_bits(account1["index"]),
            },
            {
                "項目": "子秘密鍵 (hex)",
                "index = 0": account0["private_key_hex"],
                "index = 1": account1["private_key_hex"],
            },
            {
                "項目": "公開鍵 (hex)",
                "index = 0": account0["public_key_hex"],
                "index = 1": account1["public_key_hex"],
            },
            {
                "項目": "EVMアドレス",
                "index = 0": account0["address"],
                "index = 1": account1["address"],
            },
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### ここで何が起きているか")
    st.markdown(
        """
- **シードフレーズは同じ**  
- **seed も同じ**  
- **base path も同じ**  
- 違うのは、最後の **address index** だけです  

ここで重要なのは、`/0` と `/1` が単なるラベル違いではないことです。  
BIP-32 系の子鍵導出では、この index が 4 byte の整数として計算入力に入るため、`00000000` と `00000001` の違いが、そのまま別の子鍵につながります。  
その結果、子秘密鍵・公開鍵・アドレスは、見た目にもまったく別の文字列になります。
"""
    )

    st.markdown("## index = 0 / 1 / 2 を一覧で見る")
    account_cols = st.columns(3)
    for idx, account in enumerate(metamask_accounts):
        with account_cols[idx]:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="inner-title">index = {account["index"]}</div>
    <div class="tiny">Full path</div>
    <div class="mono wrap">{account["path"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">Address</div>
    <div class="mono wrap">{account["address"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">Public key</div>
    <div class="mono wrap">{mask_middle(account["public_key_hex"], left=20, right=20)}</div>
</div>
""",
                unsafe_allow_html=True,
            )

st.divider()
st.caption(
    "教育目的の可視化アプリです。固定ダミー mnemonic のみを使っており、ウォレットではありません。"
)