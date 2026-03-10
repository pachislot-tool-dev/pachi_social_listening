# Pachi Social Listening Tool 🎰

5chのスレッドからパチスロ機種の評判を自動収集し、Gemini APIを使用して感情分析を行うツールです。
2026年3月の5chドメイン変更（.io）に完全対応済み。

## 🌟 主な機能

- **最新ドメイン対応**: `5ch.io` からのスレッド取得・解析をサポート。
- **AI感情分析**: Google Gemini API（Flash/Pro）を活用した高度なレス分析。
- **時系列トレンド**: 日次・時間ごとのユーザー感情の推移を視覚化。
- **重複排除機能**: 表記揺れによる同一スレッドの二重取得・API無駄撃ちを自動回避。
- **Streamlitダッシュボード**: 分析結果を直感的にブラウザで閲覧・管理。

## 🚀 セットアップ

1. **仮想環境の作成**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
