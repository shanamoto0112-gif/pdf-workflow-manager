import os
import json
import re
import time
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import google.genai as genai
from google.genai import types
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pypdf import PdfWriter, PdfReader

# =============================================================================
# ApiKeyManager クラス（拡張性確保：将来の複数キー対応を想定）
# =============================================================================

class ApiKeyManager:
    """
    API キーを管理するクラス。
    現在は単一キーで運用しながら、将来的に複数キー対応を容易にする設計。
    """
    
    def __init__(self, api_keys: Optional[List[str]] = None):
        """
        Args:
            api_keys: APIキーのリスト。Noneの場合は環境変数から自動取得。
        """
        if api_keys:
            self.api_keys = api_keys
        else:
            # GEMINI_API_KEYS を優先し、なければ GEMINI_API_KEY をフォールバック
            api_key_str = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
            self.api_keys = [key.strip() for key in api_key_str.split(",") if key.strip()]
        
        if not self.api_keys:
            raise ValueError(
                "API キーが設定されていません。"
                "環境変数 GEMINI_API_KEY を設定してください。"
            )
        
        self.current_index = 0  # ラウンドロビン用のインデックス
    
    def get_current_key(self) -> str:
        """現在のAPIキーを返す。"""
        return self.api_keys[self.current_index]
    
    def switch_to_next_key(self) -> bool:
        """
        次のAPIキーに切り替える。
        複数キーがある場合のみ切り替え可能。
        
        Returns:
            切り替え可能な場合 True、複数キーがない場合 False
        """
        if len(self.api_keys) == 1:
            
            return False
        self.current_index = (self.current_index + 1) % len(self.api_keys)
        return True
    
    def create_client(self) -> genai.Client:
        """
        現在のAPIキーを使用して Gemini クライアントを生成。
        
        Returns:
            genai.Client インスタンス
        """
        os.environ["GEMINI_API_KEY"] = self.get_current_key()
        return genai.Client()


# =============================================================================
# ユーティリティ関数
# =============================================================================

def ensure_dir_exists(path: Path) -> None:
    """指定されたディレクトリが存在しない場合、自動で作成する."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        print(f"ディレクトリを作成しました: {path}")


def sanitize_filename(filename: str) -> str:
    """ファイル名に使えない禁止文字をアンダースコア (_) に置換する (安全設計)."""
    # Windows/Linux/macOSで共通の禁止文字を対象
    illegal_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(illegal_chars, '_', filename)
    return sanitized.strip()


def sanitize_customer_name(customer_name: str) -> str:
    """顧客名から企業形態を削除し、余分なスペースを除去する (拡張性確保)."""
    # 削除対象の企業形態（後から拡張可能）
    company_types = ["株式会社", "有限会社"]
    
    sanitized = customer_name
    for company_type in company_types:
        sanitized = sanitized.replace(company_type, "")
    
    # 余分なスペースを削除
    sanitized = sanitized.strip()
    return sanitized


# =============================================================================
# PDF 解析関数（Gemini Vision API）
# =============================================================================

def analyze_pdf(
    client: genai.Client,
    file_path: Path,
    prompt: str,
    schema: types.Schema,
    model_name: str = "gemini-2.0-flash",
    max_retries: int = 3,
) -> tuple[Optional[Dict[str, Any]], bool]:
    """
    PDFファイルをGemini APIに送信し、構造化されたJSON形式の解析結果を取得する。
    429エラーに対して指数バックオフでリトライする。
    処理後にアップロードされた一時ファイルを削除する。
    
    Args:
        client: genai.Client インスタンス
        file_path: 解析対象のPDFファイルパス
        prompt: プロンプトテンプレート
        schema: JSON スキーマ定義
        model_name: 使用するモデル名（デフォルト: gemini-2.0-flash）
        max_retries: 最大リトライ回数（デフォルト: 3）
    
    Returns:
        解析結果の辞書（失敗時は None）と、最終的に429エラーで失敗したかを示すブール値
    """
    print(f"-> 解析開始: {file_path.name}")
    uploaded_file = None

    for attempt in range(max_retries):
        try:
            # 1. PDFファイルを一時的にアップロード (Gemini Vision機能利用)
            uploaded_file = client.files.upload(file=str(file_path))
            print(f"   一時ファイルID: {uploaded_file.name}")

            # 2. プロンプト、ファイル、JSONスキーマを指定してリクエスト
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, uploaded_file],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

            # 3. レスポンスからJSONを抽出
            if not response.text:
                print(f"   <- 警告: Geminiから有効なテキスト応答がありませんでした: {file_path.name}")
                return None, False
                
            analysis_result = json.loads(response.text)
            print(f"   <- 解析完了 (JSON取得)")
            # 後続処理のために元のファイルパスを結果に追加
            analysis_result["original_path"] = file_path
            return analysis_result, False  # 正常終了

        except Exception as e:
            # 429 エラー (クォータ超過) の特別な処理
            if hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 429 and attempt < max_retries - 1:
                # API応答に含まれる推奨待機時間 (Retry-After) を取得試行
                retry_after_seconds = 0
                # エラーメッセージから 'retryDelay' を抽出するロジック (簡易的な抽出)
                match = re.search(r"'retryDelay': '(\d+)s'", str(e))
                if match:
                    # 秒単位 (例: 27s) を整数に変換
                    retry_after_seconds = int(match.group(1)) + 1  # 1秒余裕を持たせる
                elif 'Please retry in' in str(e):
                    # メッセージから秒数を抽出する (例: 27.544816512s)
                    match_msg = re.search(r"Please retry in (\d+\.?\d*)s\.", str(e))
                    if match_msg:
                        retry_after_seconds = int(float(match_msg.group(1))) + 1

                # 指数バックオフの計算: 2^(attempt+1) を基本待機時間とする
                base_wait_time = 2.0
                exponential_wait = base_wait_time ** (attempt + 1)  # 試行0: 2s, 試行1: 4s, 試行2: 8s
                
                # 取得した推奨時間、指数バックオフ、最低60秒待機の中で最も大きい値を採用
                wait_time = max(retry_after_seconds, exponential_wait, 60.0)  # 最低60秒待機を適用
                
                print(f"   <- リトライ: Gemini APIクォータ超過 (429)。{attempt + 1}/{max_retries} 回目。{wait_time} 秒待機します。")
                time.sleep(wait_time)
                continue  # ループの最初に戻り、リトライ
            
            # 429 以外のエラー、または最大リトライ回数に達した場合
            print(f"   <- エラー: Gemini APIエラーが発生しました ({file_path.name}): {e}")
            # 最終リトライでも429の場合、呼び出し元にキー切り替えを指示するためフラグを立てる
            is_429 = hasattr(e, 'response') and hasattr(e.response, 'status_code') and e.response.status_code == 429
            return None, is_429
        except json.JSONDecodeError as e:
            print(f"   <- エラー: Geminiからの応答が不正なJSONでした ({file_path.name}): {e}")
            return None, False
        except Exception as e:
            print(f"   <- エラー: 予期せぬエラーが発生しました ({file_path.name}): {e}")
            return None, False
        finally:
            # 4. アップロードした一時ファイルを削除 (クリーンアップ)
            if uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                    print(f"   一時ファイル削除: {uploaded_file.name}")
                except Exception as e:
                    print(f"   !! 警告: 一時ファイルの削除に失敗しました: {e}")

    return None, False  # 全リトライが失敗し、最終的な429ではない場合


# =============================================================================
# メール送信関数
# =============================================================================

def send_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    subject: str,
    body: str,
    pdf_paths: List[Path],
) -> bool:
    """
    Gmailを経由してメールを送信し、複数のPDFを添付する。
    成功時は True、失敗時は False を返す。
    
    Args:
        sender_email: 送信元メールアドレス
        sender_password: Gmailアプリパスワード
        recipient_email: 送信先メールアドレス
        subject: メール件名
        body: メール本文
        pdf_paths: 添付するPDFファイルのパスリスト
    
    Returns:
        送信成功時 True、失敗時 False
    """
    try:
        # 1. SMTP接続設定（Gmail）
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # 2. メールオブジェクトの作成
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = subject
        
        # 3. メール本文を追加
        message.attach(MIMEText(body, "plain", "utf-8"))
        
        # 4. PDFファイルを添付
        for pdf_path in pdf_paths:
            if not pdf_path.exists():
                print(f"   !! 警告: PDFファイルが見つかりません: {pdf_path}")
                continue
            with open(pdf_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {pdf_path.name}")
            message.attach(part)
        
        # 5. SMTP接続してメール送信
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # TLS暗号化
            server.login(sender_email, sender_password)
            server.send_message(message)
        
        file_count = len([p for p in pdf_paths if p.exists()])
        print(f"   ✉️  メール送信完了: {recipient_email} ({file_count}件のファイルを添付)")
        return True
    
    except smtplib.SMTPAuthenticationError:
        print(f"   !! エラー: Gmail認証失敗。App Passwordが正しいか確認してください。")
        return False
    except smtplib.SMTPException as e:
        print(f"   !! エラー: メール送信失敗 (SMTP): {e}")
        return False
    except Exception as e:
        print(f"   !! エラー: メール送信中に予期せぬエラーが発生しました: {e}")
        return False


# =============================================================================
# ファイル操作関数
# =============================================================================

def move_to_failed_dir(pdf_path: Path, failed_dir: Path) -> None:
    """
    PDFファイルを failed_pdfs ディレクトリに移動する。
    
    Args:
        pdf_path: 移動対象のファイルパス
        failed_dir: 失敗ディレクトリのパス
    """
    try:
        ensure_dir_exists(failed_dir)
        failed_path = failed_dir / pdf_path.name
        shutil.move(str(pdf_path), str(failed_path))
        print(f"   → {failed_dir.name} に移動しました")
    except Exception as e:
        print(f"   !! 警告: ファイルの移動に失敗しました: {e}")


# =============================================================================
# PDF 結合関数
# =============================================================================

def combine_pdfs(pdf_paths: List[Path], output_path: Path) -> bool:
    """
    複数のPDFファイルをpypdfを使用して結合し、指定されたファイル名で保存する。
    
    Args:
        pdf_paths: 結合対象のPDFファイルパスのリスト
        output_path: 出力ファイルのパス
    
    Returns:
        結合成功時 True、失敗時 False
    """
    writer = PdfWriter()
    successfully_processed = 0
    
    for path in pdf_paths:
        try:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
            successfully_processed += 1
        except Exception as e:
            # ファイル読み込み失敗時のエラーハンドリング
            print(f"   !! 警告: PDFファイルの読み込みエラー ({path.name}) - スキップします: {e}")
            continue

    if len(writer.pages) > 0:
        try:
            # 出力ディレクトリが存在しない場合は作成
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as output_file:
                writer.write(output_file)
            print(f"   ++ ファイル結合・保存完了: {output_path.name} ({successfully_processed}ファイルを結合、{len(writer.pages)}ページ)")
            return True
        except Exception as e:
            print(f"   !! エラー: ファイル保存に失敗しました: {e}")
            return False
    else:
        print(f"   -- 結合対象の有効なページがありませんでした。保存をスキップします。")
        return False
