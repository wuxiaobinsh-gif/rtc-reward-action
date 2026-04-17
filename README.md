# RTC Reward Action

A GitHub Action that automatically awards RTC tokens to contributors when their pull requests are merged.

## Features

- **Automated Rewards**: Automatically transfers RTC tokens when PRs are merged
- **Flexible Wallet Discovery**: Reads wallet addresses from PR body or `.rtc-wallet` file
- **Dry Run Mode**: Test the action without making actual transfers
- **GitHub Integration**: Posts comments on PRs with reward details
- **Secure Signing**: Uses Ed25519 signatures for transaction security

## Usage

### Basic Setup

Create a workflow file (e.g., `.github/workflows/rtc-reward.yml`):

```yaml
name: RTC Reward

on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Award RTC Reward
        uses: your-org/rtc-reward-action@v1
        with:
          rtc_amount: 10
          node_url: https://50.28.86.131
          miner_id: your-miner-id
          private_key: ${{ secrets.RTC_PRIVATE_KEY }}
```

### With Dry Run Mode

```yaml
- name: Test Reward (Dry Run)
  uses: your-org/rtc-reward-action@v1
  with:
    rtc_amount: 10
    node_url: https://50.28.86.131
    miner_id: your-miner-id
    private_key: ${{ secrets.RTC_PRIVATE_KEY }}
    dry_run: true
```

## Configuration

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `rtc_amount` | Yes | 10 | Amount of RTC tokens to award per merged PR |
| `node_url` | Yes | https://50.28.86.131 | RTC Node URL for wallet operations |
| `miner_id` | Yes | - | Miner ID for wallet authentication |
| `private_key` | Yes | - | Ed25519 private key (base64 encoded) for signing transactions |
| `dry_run` | No | false | Run without making actual transfers |

### Wallet Address Discovery

The action looks for the contributor's wallet address in this order:

1. **PR Body**: Searches for patterns like:
   - `wallet: <address>`
   - `rtc-wallet: <address>`
   - `RTC wallet: <address>`
   - `**Wallet:** <address>`

2. **`.rtc-wallet` file**: If no wallet in PR body, fetches from repository root

### Outputs

| Output | Description |
|--------|-------------|
| `recipient_wallet` | The wallet address that received the reward |
| `amount` | The amount of RTC tokens transferred |
| `tx_hash` | The transaction hash of the transfer |

## Setting Up Secrets

1. Go to your repository's **Settings** > **Secrets**
2. Add the following secrets:
   - `RTC_PRIVATE_KEY`: Your Ed25519 private key (base64 encoded)
   - `RTC_MINER_ID`: Your miner ID

## GitHub Marketplace

This action is published on the [GitHub Marketplace](https://github.com/marketplace) and can be found by searching for "RTC Reward".

## License

MIT License - see LICENSE file for details.
