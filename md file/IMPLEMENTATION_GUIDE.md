# PDF統合処理システム - 実装・運用ガイド

## 📋 目次
1. [システム概要](#システム概要)
2. [インストール手順](#インストール手順)
3. [実行方法](#実行方法)
4. [ワークフロー詳細](#ワークフロー詳細)
5. [トラブルシューティング](#トラブルシューティング)
6. [拡張方法](#拡張方法)

---

## システム概要

### 🎯 概要
複数のPDF処理ワークフローを統一アーキテクチャで管理するシステム。

### ✨ 特徴
- **統一管理**: 3つのワークフロー（warranty, maintenance, pdf_merge）を1つのエンジンで制御
- **拡張性**: 新しいワークフロー追加が容易（BaseWorkflowを継承するだけ）
- **エラーハンドリング**: API エラー自動リトライ、解析失敗ファイル自動分類
- **複数PC対応**: config.env で環境変数を一元管理

### 📦 ワークフロー一覧

| ワークフロー | 機能 | 入力 | 出力 | メール送信 |
|-----------|------|------|------|---------|
| **warranty** | 保証修理請求書のリネーム | input_pdfs/ | output_pdfs/ | ✅ |
| **maintenance** | メンテナンス請求書のリネーム | input_pdfs/ | output_pdfs/ | ✅ |
| **pdf_merge** | PDFをグループ化して結合 | input_pdfs_merge/ | output_pdfs_merge/ | ❌ |

---

## インストール手順

### 前提条件
- Python 3.8以上
- pip（Pythonパッケージマネージャー）
- Gmail アカウント（メール送信機能使用時）
- Gemini API キー

### ステップ1: プロジェクトダウンロード

```bash
# プロジェクトディレクトリに移動
cd path/to/pdf-processing-system
```

### ステップ2: 仮想環境の構築（推奨）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### ステップ3: 依存関係のインストール

```bash
pip install -r requirements.txt
```

**requirements.txt:**
```
google-genai>=0.3.0
pypdf>=4.0.0
```

### ステップ4: 設定ファイルの作成

```bash
# config.env.example をコピー
cp config.env.example config.env

# (Windows の場合)
copy config.env.example config.env
```

### ステップ5: config.env を編集

テキストエディタで `config.env` を開き、以下を設定：

```env
# 必須：すべてのワークフロー共通
GEMINI_API_KEY=your-api-key-here

# 必須：warranty, maintenance ワークフロー用
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password-here

# オプション：メール送信先を指定（省略時はデフォルト値を使用）
RECIPIENT_EMAIL_WARRANTY=warranty-team@example.com
RECIPIENT_EMAIL_MAINTENANCE=maintenance-team@example.com
```

#### APIキーの取得

**1. Gemini API キー**
- https://ai.google.dev/gemini-api にアクセス
- 「Get API Key」をクリック
- Google アカウントにログイン
- API キーをコピー

**2. Gmail アプリパスワード**
- https://myaccount.google.com/apppasswords にアクセス
- Google アカウント（2段階認証必須）にログイン
- 「アプリを選択」で「メール」、「デバイスを選択」で「Windows PC」などを選択
- 生成されたパスワード（16文字）をコピー
- このパスワードを GMAIL_APP_PASSWORD に設定

---

## 実行方法

### Windows での実行

#### 方法1: 統一バッチファイル（推奨）

```bash
process_invoices_updated.bat
```

メニューから実行するワークフローを選択：
```
1) Warranty          - Process warranty repair invoices
2) Maintenance       - Process maintenance invoices
3) PDF Merge         - Merge and group PDFs by order number
4) Exit
```

#### 方法2: ワークフロー専用バッチ

```bash
# Warranty 処理
warranty_rename.bat

# Maintenance 処理
maintenance_rename.bat

# PDF 結合
pdf_merge.bat
```

#### 方法3: コマンドライン直接実行

```bash
python main_processor.py warranty
python main_processor.py maintenance
python main_processor.py pdf_merge

# 利用可能なワークフロー一覧
python main_processor.py --list
```

### macOS/Linux での実行

#### 方法1: 統一シェルスクリプト（推奨）

```bash
bash process_invoices.sh
```

メニューから実行するワークフローを選択。

#### 方法2: ワークフロー専用スクリプト

```bash
# PDF 結合
bash pdf_merge.sh
```

#### 方法3: コマンドライン直接実行

```bash
python3 main_processor.py warranty
python3 main_processor.py maintenance
python3 main_processor.py pdf_merge

# 利用可能なワークフロー一覧
python3 main_processor.py --list
```

---

## ワークフロー詳細

### 📄 Warranty ワークフロー

**目的**: 保証修理請求書を抽出情報に基づいてリネーム

**入力フォルダ**: `input_pdfs/`
**出力フォルダ**: `output_pdfs/`
**失敗フォルダ**: `failed_pdfs/`

**抽出項目**:
- `workorder_no`: ワークオーダー番号（8桁）
- `chassis_number`: 車台番号

**ファイル名形式**:
```
WOno.{workorder_no}_Ch.#{chassis_last_7}.pdf

例: WOno.19120401_Ch.#1234567.pdf
```

**メール設定**:
- チャンクサイズ: 1件（1件ずつ送信）
- 件名例: `#保証修理請求書/WOno.19120401/Ch.#1234567`

---

### 🔧 Maintenance ワークフロー

**目的**: メンテナンス請求書を抽出情報に基づいてリネーム

**入力フォルダ**: `input_pdfs/`
**出力フォルダ**: `output_pdfs/`
**失敗フォルダ**: `failed_pdfs/`

**抽出項目**:
- `customer_name`: 顧客名
- `chassis_number`: 車台番号
- `work_item`: 作業内容

**ファイル名形式**:
```
{customer_name}/{chassis_last_7}/{work_item}/請求書.pdf

例: マルニ/1234567/Rメンテナンス/請求書.pdf
```

**メール設定**:
- チャンクサイズ: 10件（複数件をまとめて送信）
- 件名例: `【メンテナンス請求】マルニ 02月15日送信分 (1/3)`

---

### 🔀 PDF Merge ワークフロー

**目的**: 複数のPDFを注文番号でグループ化し、結合

**入力フォルダ**: `input_pdfs_merge/`
**出力フォルダ**: `output_pdfs_merge/`
**失敗フォルダ**: `failed_pdfs_merge/`

**抽出項目**:
- `group_id`: グループID（注文番号）
- `order_number`: 注文番号
- `staff_code`: 担当コード
- `chassis_number`: 車台番号（オプション）
- `customer_name`: 顧客名（オプション）

**処理フロー**:
1. すべてのPDFを解析し、各ファイルの情報を抽出
2. 注文番号（group_id）でグループ化
3. グループごとに複数ファイルをpypdfで結合
4. ファイル名を生成してフォルダに保存

**ファイル名形式**:
```
{folder_name}/{file_name}.pdf

例:
- 車台番号がある場合: 5740828/K260121-05_#5740828.pdf
- 車台番号がない場合: マルニ在庫/K260121-05_マルニ在庫.pdf
```

**特徴**:
- メール送信なし（ローカル管理のみ）
- グループ化により複数ファイルを効率的に管理
- 自動フォルダ作成で整理が容易

---

## トラブルシューティング

### エラー: "Python not found"

**原因**: Pythonがインストールされていない、またはPATHに追加されていない

**解決策**:
1. Python をダウンロード（https://www.python.org）
2. インストール時に「Add Python to PATH」をチェック
3. コンピュータを再起動
4. 再度バッチファイルを実行

### エラー: "config.env file not found"

**原因**: config.env が存在しない

**解決策**:
```bash
# Windows
copy config.env.example config.env

# macOS/Linux
cp config.env.example config.env
```

### エラー: "GEMINI_API_KEY not set"

**原因**: config.env の GEMINI_API_KEY が空または設定されていない

**解決策**:
1. config.env をテキストエディタで開く
2. `GEMINI_API_KEY=your-gemini-api-key-here` の部分を実際のAPIキーに置き換え
3. 保存してスクリプトを再実行

### エラー: "Gmail authentication failed"

**原因**: GMAIL_EMAIL または GMAIL_APP_PASSWORD が不正

**解決策**:
1. GMAIL_EMAIL が正しいGmailアドレスか確認
2. GMAIL_APP_PASSWORD は通常のパスワードではなく、アプリパスワードを使用
3. 2段階認証が有効か確認

### エラー: "429 Too Many Requests"

**原因**: Gemini API のレート制限に達した

**解決策**:
- システムが自動的に指数バックオフでリトライ（最大3回）
- 複数のAPIキーがある場合は自動的に切り替え
- 手動の場合は少し待ってから再実行

### エラー: "PDF file read failed"

**原因**: 入力PDFが破損している、または形式が不正

**解決策**:
1. PDFファイルを別のPDFリーダーで開けるか確認
2. 破損したファイルは削除または修復
3. failed_pdfs フォルダを確認（解析失敗ファイルが自動移動される）

---

## 拡張方法

### 新しいワークフローの追加（3〜6ヶ月後）

#### ステップ1: workflows.py に新クラスを追加

```python
from workflows import BaseWorkflow
from google.genai import types

class MyCustomWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__()
        # カスタムディレクトリを設定（オプション）
        self.input_dir = Path("input_pdfs_custom")
        self.output_dir = Path("output_pdfs_custom")
        self.failed_dir = Path("failed_pdfs_custom")
    
    def get_schema(self) -> types.Schema:
        """JSON スキーマを定義"""
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "field1": types.Schema(type=types.Type.STRING, description="フィールド1"),
                "field2": types.Schema(type=types.Type.STRING, description="フィールド2"),
                "is_valid": types.Schema(type=types.Type.BOOLEAN, description="有効性フラグ"),
            },
            required=["field1", "field2", "is_valid"],
        )
    
    def get_prompt(self) -> str:
        """Gemini プロンプトを定義"""
        return """
あなたはPDF抽出エキスパートです。
以下の情報を抽出してください:
- field1: 説明
- field2: 説明
"""
    
    def generate_filename(self, analysis_result) -> str:
        """ファイル名を生成"""
        field1 = analysis_result.get("field1", "")
        field2 = analysis_result.get("field2", "")
        return f"{field1}_{field2}"
    
    def get_email_config(self):
        """メール設定（不要な場合は None）"""
        return None  # またはメール設定辞書
    
    def get_email_subject(self, result, chunk_info=None) -> str:
        """メール件名"""
        return "カスタムワークフロー完了"
    
    def get_email_body(self) -> str:
        """メール本文"""
        return "処理が完了しました。"
```

#### ステップ2: WORKFLOWS_CONFIG に登録

```python
# workflows.py の最後
WORKFLOWS_CONFIG["my_custom"] = MyCustomWorkflow()
```

#### ステップ3: 実行

```bash
python main_processor.py my_custom
```

### APIキーの複数管理

```python
# 環境変数でカンマ区切り
GEMINI_API_KEY=key1,key2,key3

# システムが自動的に複数キーを管理し、
# 429 エラー時に次のキーに切り替え
```

---

## 📊 パフォーマンスと最適化

### PDF解析の速度
- 単一PDFの解析: 平均 5〜10秒（Gemini APIの応答時間による）
- バッチ処理: 最大3つの同時リトライで効率化

### メモリ使用量
- PDF結合時: 結合ファイル総容量 + メモリバッファ（通常 100MB以下）
- 大規模ファイルの場合は順次処理

### API レート制限
- 無料プラン: 1分あたり15リクエスト
- 有料プラン: より高い制限
- 自動リトライで対応（待機時間: 5〜60秒）

---

## 📝 ログと監視

処理中にはリアルタイムでログが出力されます：

```
-> 解析開始: document1.pdf
   一時ファイルID: files/abc123
   <- 解析完了 (JSON取得)
++ リネーム・保存完了: output.pdf

[グループ処理] ID: ORD001 / ファイル数: 3
   ++ ファイル結合・保存完了: merged.pdf (3ファイルを結合、25ページ)
```

### failed_pdfs フォルダ

解析に失敗したPDFは自動的に failed_pdfs フォルダに移動され、以下の情報で確認できます：
- 移動されたファイル名
- 移動理由（is_valid=false など）

---

## 🔐 セキュリティ

### API キー
- config.env にのみ保存（.gitignore に追加推奨）
- スクリプトにハードコードしない
- 定期的にローテーション

### Gmail パスワード
- アプリパスワード（通常パスワードではない）を使用
- config.env で管理
- 漏洩時は Google アカウント設定から削除

### ファイル管理
- 入力PDFは input_pdfs フォルダのみから読み込み
- 出力PDFはサニタイズされたファイル名で保存
- 一時ファイルは自動削除

---

## 📞 サポート

問題が発生した場合：

1. **ログを確認**: コンソール出力に詳細が表示されます
2. **failed_pdfs を確認**: 解析失敗ファイルが移動されていないか確認
3. **config.env を確認**: APIキーと認証情報が正しく設定されているか確認
4. **インターネット接続**: Gemini API と Gmail サーバーへの接続確認

---

**更新日**: 2025年2月
**バージョン**: 1.0 (pdf_merge ワークフロー統合版)
