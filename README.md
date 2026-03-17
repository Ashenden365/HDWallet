# Mnemonic → Address Visualizer

Educational Streamlit app for visualizing, step by step, how the same **dummy** BIP-39 mnemonic can deterministically branch into:

- EVM address
- TRON address
- Solana address

## Safety

This app is for **education only**.

- It intentionally uses a fixed **dummy mnemonic**
- Do **not** paste a real seed phrase into any derivative of this app
- This is **not** a wallet

## What it shows

1. 12-word mnemonic structure
2. 132-bit representation
3. Entropy vs checksum
4. BIP-39 seed generation with UTF-8 NFKD normalization + PBKDF2-HMAC-SHA512
5. Path-based key derivation
6. Public key → address conversion for:
   - EVM
   - TRON
   - Solana

## Default paths

- EVM: `m/44'/60'/0'/0/0`
- TRON: `m/44'/195'/0'/0/0`
- Solana: `m/44'/501'/0'/0'`

## Notes

- EVM / TRON use `secp256k1`
- Solana uses `ed25519`
- In this app, Solana derivation is restricted to hardened segments only
- The Solana path above is the educational default adopted by this app

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```
