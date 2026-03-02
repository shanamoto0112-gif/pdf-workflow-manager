import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from google.genai import types
from core_utils import (
    analyze_pdf,
    send_email,
    sanitize_filename,
    sanitize_customer_name,
    move_to_failed_dir,
    ensure_dir_exists,
)

# =============================================================================
# ワークフロー基底クラス
# =============================================================================

class BaseWorkflow:
    """すべてのワークフローの基底クラス。共通のインターフェースを定義。"""
    
    def __init__(self):
        self.input_dir = Path("input_pdfs")
        self.output_dir = Path("output_pdfs")
        self.failed_dir = Path("failed_pdfs")
        self.model_name = "gemini-2.0-flash"
    
    def get_schema(self) -> types.Schema:
        """JSONスキーマを返す。サブクラスで実装。"""
        raise NotImplementedError
    
    def get_prompt(self) -> str:
        """プロンプトテンプレートを返す。サブクラスで実装。"""
        raise NotImplementedError
    
    def generate_filename(self, analysis_result: Dict[str, Any]) -> str:
        """
        解析結果からファイル名を生成する。サブクラスで実装。
        
        Args:
            analysis_result: Gemini から得た解析結果
        
        Returns:
            生成されたファイル名（拡張子なし）
        """
        raise NotImplementedError
    
    def get_email_config(self) -> Dict[str, str]:
        """
        メール送信の設定を返す。
        
        Returns:
            {
                "recipient_env_var": 環境変数名,
                "default_recipient": デフォルト送信先,
                "chunk_size": 1回のメールに含める件数
            }
        """
        raise NotImplementedError
    
    def get_email_subject(self, analysis_result: Dict[str, Any], chunk_info: Optional[Dict[str, int]] = None) -> str:
        """
        メール件名を生成する。サブクラスで実装。
        
        Args:
            analysis_result: Gemini から得た解析結果
            chunk_info: {"current": 現在のチャンク番号, "total": 総チャンク数}
        
        Returns:
            メール件名
        """
        raise NotImplementedError
    
    def get_email_body(self) -> str:
        """
        メール本文（テンプレート）を返す。サブクラスで実装。
        
        Returns:
            メール本文
        """
        raise NotImplementedError


# =============================================================================
# Maintenance ワークフロー
# =============================================================================

class MaintenanceWorkflow(BaseWorkflow):
    """メンテナンス部署用のワークフロー。"""
    
    def get_schema(self) -> types.Schema:
        """メンテナンス用の JSON スキーマを定義。"""
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "customer_name": types.Schema(
                    type=types.Type.STRING,
                    description="御得意先欄から抽出した顧客名。『様』を含まない (例: 株式会社 マルニ)"
                ),
                "chassis_number": types.Schema(
                    type=types.Type.STRING,
                    description="請求書から抽出した車台番号全体 (例: YS2R4X20001234567)"
                ),
                "work_item": types.Schema(
                    type=types.Type.STRING,
                    description="作業内容から抽出した作業項目。『スカニア』を含まない (例: Rメンテナンス)"
                ),
                "is_valid": types.Schema(
                    type=types.Type.BOOLEAN,
                    description="解析対象として有効なPDFかどうかのフラグ"
                ),
            },
            required=["customer_name", "chassis_number", "work_item", "is_valid"],
        )
    
    def get_prompt(self) -> str:
        """メンテナンス用のプロンプトテンプレート。"""
        return """
あなたは請求書PDFの抽出エキスパートです。以下のPDFの内容を解析し、指定されたJSONスキーマに従って必要な情報を抽出してください。

請求書の構造:
1. 顧客情報ブロック（左側）
   - 「御得意先」欄のすぐ下の行に記載されている
   - その下には「登録番号」欄がある
2. 車両情報ブロック
   - 「車台番号」という欄があり、その下に英大文字＋数字の車台番号がある (例: YS2R4X20001234567)
3. 作業内容ブロック
   - 「作業内容・使用部品名」というヘッダーがある
   - 最初の行に作業項目が記載されている (例: スカニアRメンテナンス)
   - 作業項目から『スカニア』を削除して抽出する (例: Rメンテナンス)

抽出対象:
- customer_name: 「御得意先」欄の下に記載されている顧客名。『様』を削除 (例: 株式会社 XXXX)
- chassis_number: 「車台番号」欄の下に記載されている車台番号全体 (例: YS2R4X20001234567)
- work_item: 「作業内容・使用部品名」の最初の行の作業項目。『スカニア』を削除 (例: Rメンテナンス)

注意事項:
- 3つのフィールドすべてが抽出できない場合は、is_valid を false に設定してください。
- 文字列は正確に抽出し、余分な空白やフォーマット誤りがないか確認してください。

提供されたPDFの内容に基づいて、JSON形式で返答してください。
"""
    
    def generate_filename(self, analysis_result: Dict[str, Any]) -> str:
        """
        メンテナンス用のファイル名を生成。
        形式: {customer_name}/{chassis_last_7}/{work_item}/請求書
        """
        customer_name = analysis_result.get("customer_name", "").strip()
        chassis_number = analysis_result.get("chassis_number", "").strip()
        work_item = analysis_result.get("work_item", "").strip()
        
        # 車台番号の下7桁を抽出
        chassis_last_7 = chassis_number[-7:] if len(chassis_number) >= 7 else chassis_number
        
        # ファイル名生成
        sanitized_customer_name = sanitize_customer_name(customer_name)
        base_filename = f"{sanitized_customer_name}/{chassis_last_7}/{work_item}/請求書"
        sanitized_filename = sanitize_filename(base_filename)
        return sanitized_filename
    
    def get_email_config(self) -> Dict[str, str]:
        """メンテナンスのメール設定。"""
        return {
            "recipient_env_var": "RECIPIENT_EMAIL_MAINTENANCE",
            "default_recipient": "maintenance.japan@example.com",
            "chunk_size": 10,  # 1回のメール送信につき10ファイル
        }
    
    def get_email_subject(self, analysis_result: Dict[str, Any], chunk_info: Optional[Dict[str, int]] = None) -> str:
        """メンテナンスのメール件名を生成。"""
        today = datetime.now().strftime("%m月%d日")

        # 単一ファイル送信（chunk_size=1）の場合
        if chunk_info and chunk_info["total"] == 1:
            customer_name = analysis_result.get("customer_name", "不明")
            # 件名に顧客名を含めるなど、個別の情報を利用できる
            return f"【メンテナンス請求】{customer_name} {today}送信分"
            
        # チャンク送信（chunk_size > 1）の場合
        if chunk_info:
            return f"【メンテナンス請求】マルニ {today}送信分 ({chunk_info['current']}/{chunk_info['total']})"
        
        # フォールバック (基本的に発生しない想定)
        return f"【メンテナンス請求】マルニ {today}送信分 (単体)"
    
    def get_email_body(self) -> str:
        """メンテナンスのメール本文テンプレート。"""
        return """スカニアジャパン 株式会社
Contracted Services 御中

いつもお世話になりありがとうございます。
メンテナンス契約分の請求書を送信します。
ご確認よろしくお願いいたします。

株式会社マルニ
花本
"""


# =============================================================================
# Warranty ワークフロー
# =============================================================================

class WarrantyWorkflow(BaseWorkflow):
    """WARRANTY 部署用のワークフロー。"""
    
    def get_schema(self) -> types.Schema:
        """WARRANTY 用の JSON スキーマを定義。"""
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "workorder_no": types.Schema(
                    type=types.Type.STRING,
                    description="請求書から抽出した8桁のWorkorder No. (例: 19120401)"
                ),
                "chassis_number": types.Schema(
                    type=types.Type.STRING,
                    description="請求書から抽出した車台番号 (例: YS2R4X20001234567)"
                ),
                "is_valid": types.Schema(
                    type=types.Type.BOOLEAN,
                    description="解析対象として有効なPDFかどうかのフラグ"
                ),
            },
            required=["workorder_no", "chassis_number", "is_valid"],
        )
    
    def get_prompt(self) -> str:
        """WARRANTY 用のプロンプトテンプレート。"""
        return """
あなたは請求書PDFの抽出エキスパートです。以下のPDFの内容を解析し、指定されたJSONスキーマに従って必要な情報を抽出してください。

請求書の構造:
1. 顧客住所・名前ブロック (ページ最上部)
2. 車両情報ブロック
   - 「車台番号」という欄があり、その下に英大文字＋数字の車台番号がある (例: YS2R4X20001234567)
3. 請求明細ブロック
   - 「作業内容・使用部品名」というヘッダーがある
   - 2行目に「ワークオーダーNo.xxxxxxxx」という表記がある (例: ワークオーダーNo.19120401)

抽出対象:
- workorder_no: 「ワークオーダーNo.」の後に続く8桁の数字 (例: 19120401)
- chassis_number: 「車台番号」欄の下に記載されている車台番号全体 (例: YS2R4X20001234567)

注意事項:
- 両方のフィールドが抽出できない場合は、is_valid を false に設定してください。
- 数字やフォーマットに誤りがないか確認してください。

提供されたPDFの内容に基づいて、JSON形式で返答してください。
"""
    
    def generate_filename(self, analysis_result: Dict[str, Any]) -> str:
        """
        WARRANTY 用のファイル名を生成。
        形式: WOno.{workorder_no}_Ch.#{chassis_last_7}
        """
        workorder_no = analysis_result.get("workorder_no", "").strip()
        chassis_number = analysis_result.get("chassis_number", "").strip()
        
        # 車台番号の下7桁を抽出
        chassis_last_7 = chassis_number[-7:] if len(chassis_number) >= 7 else chassis_number
        
        # ファイル名生成
        base_filename = f"WOno.{workorder_no}_Ch.#{chassis_last_7}"
        sanitized_filename = sanitize_filename(base_filename)
        return sanitized_filename
    
    def get_email_config(self) -> Dict[str, str]:
        """WARRANTY のメール設定。"""
        return {
            "recipient_env_var": "RECIPIENT_EMAIL_WARRANTY",
            "default_recipient": "warranty.japan@example.com",
            "chunk_size": 1,  # 1件ずつ送信
        }
    
    def get_email_subject(self, analysis_result: Dict[str, Any], chunk_info: Optional[Dict[str, int]] = None) -> str:
        """WARRANTY のメール件名を生成。"""
        workorder_no = analysis_result.get("workorder_no", "")
        chassis_number = analysis_result.get("chassis_number", "")
        chassis_last_7 = chassis_number[-7:] if len(chassis_number) >= 7 else chassis_number
        return f"#保証修理請求書/WOno.{workorder_no}/Ch.#{chassis_last_7}"
    
    def get_email_body(self) -> str:
        """WARRANTY のメール本文テンプレート。"""
        return """スカニアジャパン 株式会社
山川 様

いつもお世話になりありがとうございます。
保証修理の請求書を送信させていただきます。
ご確認よろしくお願いいたします。

株式会社マルニ
花本
"""


# =============================================================================
# PDF Merge ワークフロー
# =============================================================================

class PdfMergeWorkflow(BaseWorkflow):
    """
    PDF結合・グループ化ワークフロー。
    複数のPDFを注文番号でグループ化し、結合・リネームする。
    メール送信は不要（ローカル管理のみ）。
    """
    
    def __init__(self):
        """初期化時にディレクトリを設定。"""
        super().__init__()
        # merge 用の専用ディレクトリ
        self.input_dir = Path("input_pdfs_merge")
        self.output_dir = Path("output_pdfs_merge")
        self.failed_dir = Path("failed_pdfs_merge")
    
    def get_schema(self) -> types.Schema:
        """PDF結合用のJSONスキーマを定義。"""
        return types.Schema(
            type=types.Type.OBJECT,
            properties={
                "group_id": types.Schema(
                    type=types.Type.STRING,
                    description="このドキュメントを結合するグループのID。抽出した注文番号を使用する。"
                ),
                "new_filename": types.Schema(
                    type=types.Type.STRING,
                    description="AIが提案する結合後の新しいファイル名（拡張子なし）。車台番号がない場合は顧客名を使用。"
                ),
                "is_valid": types.Schema(
                    type=types.Type.BOOLEAN,
                    description="解析対象として有効なPDFかどうかのフラグ"
                ),
                "order_number": types.Schema(
                    type=types.Type.STRING,
                    description="伝票から抽出した注文番号（group_idの基になる）"
                ),
                "staff_code": types.Schema(
                    type=types.Type.STRING,
                    description="備考欄から抽出した担当コード（ファイル名に使用）"
                ),
                "chassis_number": types.Schema(
                    type=types.Type.STRING,
                    description="備考欄から抽出した車台番号。ない場合は空欄にすること。"
                ),
                "customer_name": types.Schema(
                    type=types.Type.STRING,
                    description="備考欄から抽出した顧客名（車台番号がない場合のフォールバック）"
                ),
            },
            required=["group_id", "new_filename", "is_valid", "order_number", "staff_code", "chassis_number", "customer_name"],
        )
    
    def get_prompt(self) -> str:
        """PDF結合用のプロンプトテンプレート。"""
        return """
あなたはPDFドキュメントの分類エキスパートです。以下のPDFの内容を解析し、
指定されたJSONスキーマに従って、必要な情報を抽出し、group_idとnew_filenameを決定してください。

抽出対象: 注文番号 (order_number)、担当コード (staff_code)、車台番号 (chassis_number)、顧客名 (customer_name)。
  - 備考欄のフォーマット: 担当コード #車台番号 / 顧客名 車番 (※車番はファイル名に使用しないため無視して良い)

グループ化のルール (group_id): 抽出した「注文番号 (order_number)」をそのまま使用してください。

ファイル名の決定ルール (new_filename):
  1. 車台番号 (chassis_number) が抽出できた場合: **「担当コード_車台番号」**
  2. 車台番号 (chassis_number) が抽出できなかった場合（空欄の場合）: **「担当コード_顧客名」**

例1 (車台番号がある場合): 担当コード=K260121-05, 車台番号=#5740828 の場合、new_filename=K260121-05_#5740828
例2 (車台番号がない場合): 担当コード=X260120-01, 顧客名=マルニ在庫 の場合、new_filename=X260120-01_マルニ在庫

提供されたPDFの内容に基づいて、最適な情報を抽出し、JSON形式で返答してください。
"""
    
    def generate_filename(self, analysis_result: Dict[str, Any]) -> str:
        """
        PDF結合用のファイル名を生成。
        形式: {staff_code}_{chassis_number} または {staff_code}_{customer_name}
        
        注: このメソッドは単一ファイルの出力名を生成する役割。
            実際のグループ結合はworkflow内のカスタムロジックで行う。
        """
        staff_code = analysis_result.get("staff_code", "").strip()
        chassis_number = analysis_result.get("chassis_number", "").strip()
        customer_name = analysis_result.get("customer_name", "").strip()
        
        # ファイル名生成ロジック（既存のpdf_processor.pyから移植）
        if chassis_number:
            base_filename = f"{staff_code}_{chassis_number}"
        elif customer_name:
            base_filename = f"{staff_code}_{customer_name}"
        else:
            # フォールバック（通常は発生しない想定）
            base_filename = f"{staff_code}_merged"
        
        sanitized_filename = sanitize_filename(base_filename)
        return sanitized_filename
    
    def get_email_config(self) -> Optional[Dict[str, str]]:
        """
        PDF結合ワークフローではメール送信が不要な場合の設定。
        None を返すことでメール送信をスキップする。
        
        Returns:
            None（メール送信不要）
        """
        return None
    
    def get_email_subject(self, analysis_result: Dict[str, Any], chunk_info: Optional[Dict[str, int]] = None) -> str:
        """メール件名（使用されない）。"""
        # メール送信が不要なため、このメソッドは呼ばれない想定
        return "PDF結合完了"
    
    def get_email_body(self) -> str:
        """メール本文（使用されない）。"""
        # メール送信が不要なため、このメソッドは呼ばれない想定
        return "PDF結合が完了しました。"


# =============================================================================
# ワークフロー辞書
# =============================================================================

WORKFLOWS_CONFIG: Dict[str, BaseWorkflow] = {
    "maintenance": MaintenanceWorkflow(),
    "warranty": WarrantyWorkflow(),
    "pdf_merge": PdfMergeWorkflow(),
}


def get_workflow(workflow_name: str) -> Optional[BaseWorkflow]:
    """
    ワークフロー名から対応するワークフローインスタンスを取得。
    
    Args:
        workflow_name: ワークフロー名 ("maintenance" または "warranty")
    
    Returns:
        ワークフローインスタンス、存在しない場合は None
    """
    return WORKFLOWS_CONFIG.get(workflow_name)


def list_workflows() -> List[str]:
    """
    利用可能なすべてのワークフロー名を返す。
    
    Returns:
        ワークフロー名のリスト
    """
    return list(WORKFLOWS_CONFIG.keys())
