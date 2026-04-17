#!/usr/bin/env python3
"""
RTC Reward Action - Awards RTC tokens for merged PRs
"""

import os
import sys
import json
import re
import base64
import requests
from nacl.signing import SigningKey
from nacl.encoding import RawEncoder

# GitHub Action environment
GITHUB_EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH", "/github/event.json")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_ACTOR = os.environ.get("GITHUB_ACTOR", "")

# Action inputs
RTC_AMOUNT = os.environ.get("INPUT_RTC_AMOUNT", "10")
NODE_URL = os.environ.get("INPUT_NODE_URL", "https://50.28.86.131")
MINER_ID = os.environ.get("INPUT_MINER_ID", "")
DRY_RUN = os.environ.get("INPUT_DRY_RUN", "false").lower() == "true"
PRIVATE_KEY = os.environ.get("INPUT_PRIVATE_KEY", "")


def log(msg):
    """Print formatted log message"""
    print(f"[RTC Reward] {msg}")


def set_output(name, value):
    """Set GitHub Action output"""
    with open(os.environ.get("GITHUB_OUTPUT", "/tmp/outputs"), "a") as f:
        f.write(f"{name}={value}\n")


def get_pr_body():
    """Get PR body from event payload"""
    try:
        with open(GITHUB_EVENT_PATH, "r") as f:
            event = json.load(f)
        return event.get("pull_request", {}).get("body", "") or ""
    except Exception as e:
        log(f"Error reading PR body: {e}")
        return ""


def extract_wallet_from_body(body):
    """Extract wallet address from PR body"""
    patterns = [
        r'(?:wallet|rtc(?:-?wallet)?):\s*([a-zA-Z0-9]{32,})',
        r' RTC wallet:\s*([a-zA-Z0-9]{32,})',
        r'\*\*Wallet:\*\*\s*([a-zA-Z0-9]{32,})',
    ]
    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def get_file_content(path, repo, ref, token):
    """Fetch file content from GitHub repository"""
    headers = {"Authorization": f"token {token}"} if token else {}
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8")
    except Exception as e:
        log(f"Error fetching {path}: {e}")
    return None


def post_comment(repo, pr_number, body, token):
    """Post a comment on the PR"""
    if not token:
        log("No GitHub token, skipping comment")
        return
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    data = {"body": body}
    
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        if resp.status_code in (200, 201):
            log("Comment posted successfully")
        else:
            log(f"Failed to post comment: {resp.status_code}")
    except Exception as e:
        log(f"Error posting comment: {e}")


def sign_transaction(sender, recipient, amount, private_key):
    """Sign a transaction using Ed25519"""
    try:
        # Decode base64 private key
        key_bytes = base64.b64decode(private_key)
        signing_key = SigningKey(key_bytes, encoder=RawEncoder)
        
        # Create message to sign
        message = f"{sender}:{recipient}:{amount}".encode()
        signed = signing_key.sign(message, encoder=RawEncoder)
        
        return base64.b64encode(signed.signature).decode()
    except Exception as e:
        log(f"Signing error: {e}")
        return None


def transfer_rtc(sender, recipient, amount, miner_id, private_key):
    """Transfer RTC tokens using the wallet API"""
    signature = sign_transaction(sender, recipient, amount, private_key)
    if not signature:
        return None
    
    url = f"{NODE_URL}/wallet/transfer/signed"
    payload = {
        "miner_id": miner_id,
        "sender": sender,
        "recipient": recipient,
        "amount": str(amount),
        "signature": signature
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tx_hash") or data
        else:
            log(f"Transfer failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        log(f"Transfer error: {e}")
        return None


def main():
    log("Starting RTC Reward Action")
    log(f"Node URL: {NODE_URL}")
    log(f"Dry Run: {DRY_RUN}")
    
    # Load event payload
    try:
        with open(GITHUB_EVENT_PATH, "r") as f:
            event = json.load(f)
    except Exception as e:
        log(f"Error loading event: {e}")
        sys.exit(1)
    
    # Check if PR was merged
    action = event.get("action")
    merged = event.get("pull_request", {}).get("merged", False)
    
    if action != "closed":
        log(f"Action is '{action}', waiting for 'closed'")
        sys.exit(0)
    
    if not merged:
        log("PR was closed but not merged, no reward")
        sys.exit(0)
    
    log("PR was merged! Processing reward...")
    
    pr_number = event.get("pull_request", {}).get("number", 0)
    pr_title = event.get("pull_request", {}).get("title", "Unknown PR")
    pr_body = event.get("pull_request", {}).get("body", "") or ""
    contributor = event.get("pull_request", {}).get("user", {}).get("login", "unknown")
    
    log(f"PR: #{pr_number} - {pr_title}")
    log(f"Contributor: {contributor}")
    
    # Extract wallet address
    wallet_address = extract_wallet_from_body(pr_body)
    
    if not wallet_address:
        # Try to fetch from .rtc-wallet file
        ref = event.get("pull_request", {}).get("head", {}).get("ref", "main")
        file_content = get_file_content(".rtc-wallet", GITHUB_REPOSITORY, ref, GITHUB_TOKEN)
        if file_content:
            wallet_address = extract_wallet_from_body(file_content)
    
    if not wallet_address:
        log("No wallet address found in PR body or .rtc-wallet file")
        post_comment(
            GITHUB_REPOSITORY, pr_number,
            f"## RTC Reward\n\n❌ Could not find wallet address. "
            "Please add your RTC wallet address to the PR body or create a `.rtc-wallet` file.",
            GITHUB_TOKEN
        )
        sys.exit(1)
    
    log(f"Wallet address: {wallet_address}")
    
    # Process transfer
    amount = int(RTC_AMOUNT)
    
    if DRY_RUN:
        log(f"[DRY RUN] Would transfer {amount} RTC to {wallet_address}")
        tx_hash = f"dry_run_{pr_number}_{wallet_address[:8]}"
    else:
        log(f"Transferring {amount} RTC to {wallet_address}")
        tx_hash = transfer_rtc(GITHUB_ACTOR, wallet_address, amount, MINER_ID, PRIVATE_KEY)
        
        if not tx_hash:
            log("Transfer failed!")
            post_comment(
                GITHUB_REPOSITORY, pr_number,
                f"## RTC Reward\n\n❌ Transfer failed. Please contact support.",
                GITHUB_TOKEN
            )
            sys.exit(1)
    
    # Set outputs
    set_output("recipient_wallet", wallet_address)
    set_output("amount", str(amount))
    set_output("tx_hash", str(tx_hash))
    
    # Post success comment
    dry_run_text = "**[DRY RUN]** " if DRY_RUN else ""
    comment = (
        f"## {dry_run_text}RTC Reward\n\n"
        f"✅ Successfully awarded **{amount} RTC** to `{wallet_address}`\n\n"
        f"**PR:** #{pr_number} - {pr_title}\n"
        f"**Contributor:** @{contributor}\n"
        f"**TX Hash:** `{tx_hash}`"
    )
    post_comment(GITHUB_REPOSITORY, pr_number, comment, GITHUB_TOKEN)
    
    log(f"Reward complete! TX: {tx_hash}")
    sys.exit(0)


if __name__ == "__main__":
    main()
