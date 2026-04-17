name: Daily Hugo Palmer Runner Check

on:
  schedule:
    - cron: '0 7 * * *'
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run script
        env:
          RACING_API_USERNAME: ${{ secrets.RACING_API_USERNAME }}
          RACING_API_PASSWORD: ${{ secrets.RACING_API_PASSWORD }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python fetch_runners.py

      - name: Save results
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add data/
          git diff --staged --quiet || git commit -m "Daily Hugo Palmer runners update"
          git push
