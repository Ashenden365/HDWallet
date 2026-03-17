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
    return value.to_bytes(4, "big").hex()


def format_u32_bits(value: int) -> str:
    bits = f"{value:032b}"
    return " ".join(bits[i:i + 8] for i in range(0, 32, 8))


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
    derivation_result = derive_all_chains(
        mnemonic=mnemonic,
        passphrase=passphrase,
        evm_path=evm_path,
        tron_path=tron_path,
        solana_path=solana_path,
    )
    metamask_accounts = derive_evm_account_series(
        mnemonic=mnemonic,
        passphrase=passphrase,
        base_path=metamask_base_path,
        indices=[0, 1, 2],
    )
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
    show_key_details = st.checkbox("鍵素材テーブルも表示する（マスク表示）", value=False)

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
  つまり、同じ入力と同じルールを使えば、いつでも同じ結果が再現される、という性質です。

- **「H：階層構造」タブから「MetaMask の複数アカウント」タブまでは H を中心に示しています。**  
  つまり、1つの seed から親子関係のある複数の鍵やアドレスが枝分かれして作られる、という性質です。
"""
    )

    concept_col1, concept_col2 = st.columns(2)

    with concept_col1:
        st.markdown(
            """
<div class="summary-card">
    <div class="inner-title">D = Deterministic（決定論的）</div>
    <div>
        同じシードフレーズと同じルールを使えば、いつでも同じ鍵と同じアドレスを再現できます。  
        つまり、結果が偶然ではなく、入力とルールによって決まる、ということです。
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with concept_col2:
        st.markdown(
            """
<div class="summary-card">
    <div class="inner-title">H = Hierarchical（階層的）</div>
    <div>
        鍵を親子関係のあるツリー構造として管理できる、という意味です。  
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
        "同じニーモニックと同じルールを使えば、いつでも同じ seed・同じアドレスが再現されることを見る画面です。",
    )

    st.markdown(
        """
HDウォレットの **D（Deterministic）** とは、**同じ入力と同じルールを使えば、同じ出力が再現される**という性質です。  
ここでは、固定ダミー mnemonic から共通の seed を作り、その seed から各チェーンのアドレスが決まる流れを見ます。
"""
    )

    st.markdown("## 1. ニーモニック")
    st.markdown(
        "12語のニーモニックは、単なる単語列ではありません。**128-bit の entropy と 4-bit の checksum を合わせた 132 bit** が、11-bit ずつ単語に対応づけられています。"
    )

    st.dataframe(
        build_step_rows(mnemonic_analysis),
        use_container_width=True,
        hide_index=True,
    )

    if show_bit_view:
        with st.expander("132 bit の内訳を見る", expanded=False):
            st.markdown(
                f"""
<div class="summary-card">
    <div class="inner-title">132-bit representation</div>
    <div class="mono wrap">{bits_to_grouped_string(mnemonic_analysis["all_bits"], group_size=11)}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
<div class="two-box">
    <div class="inner-box">
        <div class="inner-title">Entropy ({len(mnemonic_analysis["entropy_bits"])} bit)</div>
        <div class="mono wrap">{bits_to_grouped_string(mnemonic_analysis["entropy_bits"], group_size=8)}</div>
    </div>
    <div class="inner-box">
        <div class="inner-title">Checksum ({len(mnemonic_analysis["checksum_bits"])} bit)</div>
        <div class="mono wrap">{mnemonic_analysis["checksum_bits"]}</div>
    </div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("## 2. seed")
    st.markdown(
        "次に、ニーモニックと passphrase を **UTF-8 NFKD** に正規化したうえで、**PBKDF2-HMAC-SHA512** を使って 64-byte の seed を作ります。ここまでは EVM・TRON・Solana に共通です。"
    )

    seed_col1, seed_col2 = st.columns([1, 1])

    with seed_col1:
        st.markdown("#### 入力")
        st.dataframe(
            [
                {"項目": "ニーモニック", "値": mnemonic},
                {"項目": "passphrase", "値": "(空文字)" if passphrase == "" else passphrase},
                {"項目": "正規化", "値": seed_analysis["normalization"]},
                {"項目": "salt", "値": seed_analysis["salt_str"]},
                {"項目": "反復回数", "値": seed_analysis["iterations"]},
                {"項目": "出力長", "値": f"{seed_analysis['dklen']} byte"},
            ],
            use_container_width=True,
            hide_index=True,
        )

    with seed_col2:
        st.markdown("#### 出力")
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">Seed (64 byte)</div>
    <div class="mono wrap">{mask_middle(seed_analysis["seed_hex"], left=28, right=28)}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("## 3. 固定ルールに従うと、結果も固定される")
    st.markdown(
        """各チェーンでは、**導出パス**、**鍵生成に使う曲線**、**アドレスへの変換方式** が決まっています。  
したがって、ルールを固定すれば、出てくるアドレスも固定されます。"""
    )

    fixed_cols = st.columns(3)
    for idx, (chain_name, chain) in enumerate(derivation_result["chains"].items()):
        with fixed_cols[idx]:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="inner-title">{chain_name}</div>
    <div class="tiny">鍵生成に使う曲線</div>
    <div>{render_badge(chain["curve"], chain["curve_badge"])}</div>
    <div class="tiny" style="margin-top:0.7rem;">導出パス</div>
    <div class="mono wrap">{chain["path"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">最終アドレス</div>
    <div class="mono wrap">{chain["address"]}</div>
</div>
""",
                unsafe_allow_html=True,
            )

with compare_tab:
    render_section_header(
        "チェーン比較",
        "同じ出発点から、EVM・TRON・Solana がどこまで共通で、どこから分岐するかを比較する画面です。Solana については、このアプリで採用した教育用 path を明示しています。",
    )

    st.markdown(
        """
このタブは引き続き **D（Deterministic）** に関わっています。  
つまり、**チェーンごとのルールを固定すれば、そのチェーンのアドレスは決定論的に決まる**ということです。  
同じニーモニックから出発しても、ルールが違えば別々のアドレスが生まれます。
"""
    )

    st.dataframe(
        build_compare_rows(derivation_result["chains"]),
        use_container_width=True,
        hide_index=True,
    )

    compare_left, compare_right = st.columns(2)

    with compare_left:
        st.markdown("### 共通していること")
        st.markdown(
            """
- 同じ **12語のニーモニック** から始まる
- 同じ **BIP-39 の手順** で seed を作る
- すべて **決定論的** に鍵とアドレスが導出される
"""
        )

    with compare_right:
        st.markdown("### 主な違い")
        st.markdown(
            """
- **coin type** が違う
- **鍵生成に使う曲線** が違う
- **公開鍵の扱い方** が違う
- **アドレスへの変換方式** が違う
"""
        )

    st.markdown("### チェーンごとの説明")
    for chain_name, chain in derivation_result["chains"].items():
        st.markdown(f"#### {chain_name}")

        if chain_name == "EVM":
            st.markdown(
                """
- seed から `m/44'/60'/0'/0/0` に沿って秘密鍵を導出します  
- secp256k1 で公開鍵を作ります  
- 公開鍵に Keccak-256 をかけます  
- 下位 20 byte を取り、EIP-55 形式の `0x...` アドレスに変換します
"""
            )
        elif chain_name == "TRON":
            st.markdown(
                """
- seed から `m/44'/195'/0'/0/0` に沿って秘密鍵を導出します  
- secp256k1 で公開鍵を作ります  
- 公開鍵に Keccak-256 をかけます  
- 下位 20 byte に `41` を前置し、Base58Check 化して `T...` アドレスに変換します
"""
            )
        else:
            st.markdown(
                """
- このアプリでは、Solana 用の教育用 path として `m/44'/501'/0'/0'` を使います  
- ed25519 / SLIP-0010 系のルールに従い、**hardened segment のみ**で子鍵を導出します  
- 32 byte の公開鍵をそのまま Base58 表示します  
- その文字列が Solana アドレスになります
"""
            )

    snapshot_cols = st.columns(3)
    for idx, (chain_name, chain) in enumerate(derivation_result["chains"].items()):
        with snapshot_cols[idx]:
            st.markdown(
                f"""
<div class="summary-card">
    <div class="inner-title">{chain_name}</div>
    <div class="tiny">公開鍵</div>
    <div class="mono wrap">{mask_middle(chain["final_public_key_hex"], left=20, right=20)}</div>
    <div class="tiny" style="margin-top:0.65rem;">アドレス</div>
    <div class="mono wrap">{chain["address"]}</div>
</div>
""",
                unsafe_allow_html=True,
            )

with hierarchical_tab:
    render_section_header(
        "H：階層構造",
        "1つの seed から鍵がどのように枝分かれしていくか、導出パスの構造を通じて学ぶ画面です。",
    )

    st.markdown(
        """
ここからは **H（Hierarchical）** に注目します。  
HDウォレットでは、鍵は単発で1個だけ作られるのではなく、**親から子へと枝分かれする構造**の中で管理されます。  
その構造を表しているのが **導出パス** です。
"""
    )

    st.markdown("## 導出パスの見方")
    st.markdown(
        """
たとえば EVM の `m/44'/60'/0'/0/0` は、  
**purpose → coin type → account → change → address index**  
という階層を表しています。
"""
    )

    path_explain_col1, path_explain_col2 = st.columns([1.0, 1.0])

    with path_explain_col1:
        st.markdown(
            """
<div class="summary-card">
    <div class="inner-title">EVM の例</div>
    <div class="mono wrap">m / 44' / 60' / 0' / 0 / 0</div>
    <div class="tiny" style="margin-top:0.75rem;">
        右に進むほど、より細かい「枝」に降りていくイメージです。
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with path_explain_col2:
        st.dataframe(
            build_path_component_rows(evm_path),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("## 各チェーンの path はどのように違うか")
    path_cols = st.columns(3)
    for idx, (chain_name, chain) in enumerate(derivation_result["chains"].items()):
        with path_cols[idx]:
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

    st.markdown("## 親から子へ進む様子")
    st.markdown(
        "以下は、各チェーンで path を 1 段ずつ進んだときに、どの階層にいるかを表示したものです。"
    )

    for chain_name, chain in derivation_result["chains"].items():
        with st.expander(f"{chain_name} の path の進み方を見る", expanded=(chain_name == "EVM")):
            st.dataframe(
                build_derivation_summary_rows(chain, secret_visibility="Masked"),
                use_container_width=True,
                hide_index=True,
            )

        if show_key_details:
            with st.expander(f"{chain_name} の鍵素材を見る", expanded=False):
                st.dataframe(
                    build_key_material_rows(chain, secret_visibility="Masked"),
                    use_container_width=True,
                    hide_index=True,
                )

with metamask_tab:
    render_section_header(
        "MetaMask の複数アカウント",
        "同じ seed から index を 0 / 1 / 2 と変えたとき、EVM アドレスがどう増えるかを見る画面です。",
    )

    st.markdown(
        """
このタブは **H（Hierarchical）** を最も直感的に感じられる部分です。  
同じシードフレーズから複数アドレスが作れるのは、seed の下に複数の枝があるからです。

MetaMask が **Secret Recovery Phrase を既定の方法で import する文脈**では、  
EVM 用の base path は `m/44'/60'/0'/0` で、  
その先の **address index** を `0`, `1`, `2` ... と変えることで、別々のアドレスを順番に導出できます。
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

    compare_text_col1, compare_text_col2 = st.columns(2)

    with compare_text_col1:
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">index = 0</div>
    <div class="tiny">Full path</div>
    <div class="mono wrap">{account0["path"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">子秘密鍵</div>
    <div class="mono wrap">{account0["private_key_hex"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">公開鍵</div>
    <div class="mono wrap">{account0["public_key_hex"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">Address</div>
    <div class="mono wrap">{account0["address"]}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with compare_text_col2:
        st.markdown(
            f"""
<div class="summary-card">
    <div class="inner-title">index = 1</div>
    <div class="tiny">Full path</div>
    <div class="mono wrap">{account1["path"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">子秘密鍵</div>
    <div class="mono wrap">{account1["private_key_hex"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">公開鍵</div>
    <div class="mono wrap">{account1["public_key_hex"]}</div>
    <div class="tiny" style="margin-top:0.7rem;">Address</div>
    <div class="mono wrap">{account1["address"]}</div>
</div>
""",
            unsafe_allow_html=True,
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