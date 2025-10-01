#!/usr/bin/env python3
"""
Slack接続テストスクリプト
トークンとSocket Modeの接続を確認します
"""

import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

print("=" * 60)
print("Slack接続テスト")
print("=" * 60)

# トークンの確認
print("\n1. トークンの確認:")
print(f"   Bot Token: {SLACK_BOT_TOKEN[:20]}... ({'設定済み' if SLACK_BOT_TOKEN else '未設定'})")
print(f"   App Token: {SLACK_APP_TOKEN[:20]}... ({'設定済み' if SLACK_APP_TOKEN else '未設定'})")

if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
    print("\n❌ エラー: トークンが設定されていません")
    exit(1)

# Bot Token のテスト
print("\n2. Bot Token のテスト:")
try:
    client = WebClient(token=SLACK_BOT_TOKEN)
    response = client.auth_test()
    print(f"   ✓ 接続成功")
    print(f"   - Bot名: {response['user']}")
    print(f"   - Bot ID: {response['user_id']}")
    print(f"   - チーム: {response['team']}")
except SlackApiError as e:
    print(f"   ❌ エラー: {e.response['error']}")
    exit(1)

# チャネル一覧の取得
print("\n3. チャネルの確認:")
try:
    response = client.conversations_list(types="public_channel,private_channel")
    channels = response['channels']
    print(f"   ✓ {len(channels)}個のチャネルが見つかりました")
    
    # ボットが参加しているチャネル
    joined_channels = [ch for ch in channels if ch.get('is_member', False)]
    if joined_channels:
        print(f"\n   ボットが参加しているチャネル:")
        for ch in joined_channels:
            print(f"   - #{ch['name']} (ID: {ch['id']})")
    else:
        print("\n   ⚠️  ボットがどのチャネルにも参加していません")
        print("      Slackでチャネルにボットを追加してください")
        
except SlackApiError as e:
    print(f"   ⚠️  チャネル情報の取得に失敗: {e.response['error']}")

print("\n" + "=" * 60)
print("接続テスト完了")
print("=" * 60)

