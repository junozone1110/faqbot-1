#!/usr/bin/env python3
"""
利用可能なGeminiモデルをリストアップするスクリプト
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("エラー: .envファイルにGOOGLE_API_KEYを設定してください。")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)

print("利用可能なGeminiモデル:\n")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"  - {model.name}")
        print(f"    表示名: {model.display_name}")
        print(f"    説明: {model.description}")
        print()

