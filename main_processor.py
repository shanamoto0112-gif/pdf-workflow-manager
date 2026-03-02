import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
import shutil
from core_utils import (
    ApiKeyManager,
    analyze_pdf,
    send_email,
    move_to_failed_dir,
    ensure_dir_exists,
    sanitize_filename,
)
from workflows import get_workflow, list_workflows


# =============================================================================
# ワークフロー実行エンジン
# =============================================================================

class WorkflowEngine:
    """ワークフローを実行するメインエンジン。"""
    
    def __init__(self, workflow_name: str):
        """
        Args:
            workflow_name: ワークフロー名 ("maintenance" または "warranty")
        """
        self.workflow = get_workflow(workflow_name)
        if not self.workflow:
            raise ValueError(
                f"不正なワークフロー名: {workflow_name}\n"
                f"利用可能なワークフロー: {', '.join(list_workflows())}"
            )
        
        # APIキーマネージャーの初期化（拡張性確保）
        try:
            self.api_key_manager = ApiKeyManager()
        except ValueError as e:
            print(f"致命的エラー: {e}")
            sys.exit(1)
        
        # メール認証情報の取得
        self.sender_email = os.getenv("GMAIL_EMAIL")
        self.sender_password = os.getenv("GMAIL_APP_PASSWORD")
        
        # ワークフロー固有のメール設定を取得
        email_config = self.workflow.get_email_config()
        self.recipient_email = os.getenv(
            email_config["recipient_env_var"],
            email_config["default_recipient"]
        )
        self.chunk_size = email_config["chunk_size"]
        
        # メール認証情報の確認
        if not self.sender_email or not self.sender_password:
            print("警告: メール送信に必要な環境変数が設定されていません。")
            print("以下を設定してください:")
            print("  $env:GMAIL_EMAIL='your-email@gmail.com'")
            print("  $env:GMAIL_APP_PASSWORD='your-app-password'")
            print("メール送信をスキップしながら処理を続行します。")
            self.sender_email = None
            self.sender_password = None
        
        # ディレクトリの初期化
        ensure_dir_exists(self.workflow.input_dir)
        ensure_dir_exists(self.workflow.output_dir)
        ensure_dir_exists(self.workflow.failed_dir)
    
    def run(self) -> None:
        """ワークフロー全体を実行する。"""
        print(f"\n{'='*70}")
        print(f"ワークフロー実行: {self.workflow.__class__.__name__}")
        print(f"{'='*70}\n")
        
        # ステップ1: 入力ファイルの収集
        pdf_files = self._collect_pdf_files()
        if not pdf_files:
            return
        
        # ステップ2: PDF解析・リネーム
        output_paths = self._process_pdfs(pdf_files)
        
        # ステップ3: メール送信
        self._send_emails(output_paths)
        
        print(f"\n{'='*70}")
        print("全ての処理が完了しました")
        print(f"{'='*70}\n")
    
    def _collect_pdf_files(self) -> List[Path]:
        """
        入力ディレクトリから PDF ファイルを収集する。
        
        Returns:
            PDFファイルパスのリスト
        """
        pdf_files = sorted(list(self.workflow.input_dir.glob("*.pdf")))
        if not pdf_files:
            print(f"警告: {self.workflow.input_dir} フォルダ内にPDFファイルが見つかりませんでした。")
            return []
        
        print(f"--- {len(pdf_files)} 件のPDFファイルを検出しました ---\n")
        return pdf_files
    
    def _process_pdfs(self, pdf_files: List[Path]) -> List[Path]:
        """
        各PDFを解析し、リネーム・保存する。
        PdfMergeWorkflow の場合は、グループ化・結合処理を実行。
        
        Args:
            pdf_files: 処理対象のPDFファイルリスト
        
        Returns:
            正常に処理されたファイルパスと結果を含む辞書のリスト
        """
        output_paths = []
        processed_count = 0
        skipped_count = 0
        
        # Gemini クライアントの初期化
        client = self.api_key_manager.create_client()
        
        # PdfMergeWorkflow の場合は、グループ化・結合ロジックを実行
        if self.workflow.__class__.__name__ == "PdfMergeWorkflow":
            return self._process_pdfs_merge(pdf_files, client)
        
        # その他のワークフロー（通常のリネーム処理）
        for pdf_path in pdf_files:
            # PDF解析
            result, is_429_error = analyze_pdf(
                client,
                pdf_path,
                self.workflow.get_prompt(),
                self.workflow.get_schema(),
                model_name=self.workflow.model_name,
            )
            
            # 429エラーが発生した場合、次のAPIキーに切り替えてクライアントを再作成
            if is_429_error:
                print("🚨 429エラーを検知。APIキーを自動的に切り替えます。")
                if self.api_key_manager.switch_to_next_key():
                    client = self.api_key_manager.create_client()
                    print(f"🔑 クライアント切り替え完了。次のファイルから新しいキーを使用します。\n")
                else:
                    print("❌ APIキーが1つしかないため、切り替えできません。処理を続行します。\n")

            # 解析失敗またはis_valid = false の場合
            if not result or not result.get("is_valid", False):
                print(f"!! スキップ: {pdf_path.name} - 有効な解析結果が得られませんでした。")
                move_to_failed_dir(pdf_path, self.workflow.failed_dir)
                skipped_count += 1
                continue
            
            try:
                # ファイル名の生成（ワークフロー固有）
                sanitized_filename = self.workflow.generate_filename(result)
                output_path = self.workflow.output_dir / f"{sanitized_filename}.pdf"
                
                # PDFファイルをリネーム・保存
                shutil.copy2(pdf_path, output_path)
                print(f"++ リネーム・保存完了: {output_path.name}\n")
                # ファイルパスと解析結果をセットで保存
                output_paths.append({"path": output_path, "result": result})
                processed_count += 1
                
            except Exception as e:
                print(f"!! エラー: {pdf_path.name} の処理中に予期せぬエラーが発生しました: {e}\n")
                move_to_failed_dir(pdf_path, self.workflow.failed_dir)
                skipped_count += 1
        
        print(f"--- PDF処理完了 ---")
        print(f"処理成功: {processed_count}件 / スキップ: {skipped_count}件\n")
        
        return output_paths
    
    def _process_pdfs_merge(self, pdf_files: List[Path], client) -> List[Path]:
        """
        PdfMergeWorkflow 用の処理。
        複数PDFを注文番号でグループ化し、結合・リネームする。
        
        Args:
            pdf_files: 処理対象のPDFファイルリスト
            client: Gemini APIクライアント
        
        Returns:
            結合されたファイルパスと結果を含む辞書のリスト
        """
        from core_utils import combine_pdfs
        
        output_paths = []
        skipped_count = 0
        
        print("--- PDF結合・グループ化ワークフロー開始 ---\n")
        
        # ステップ1: 全PDFを解析
        all_analysis_results = []
        for pdf_path in pdf_files:
            result, is_429_error = analyze_pdf(
                client,
                pdf_path,
                self.workflow.get_prompt(),
                self.workflow.get_schema(),
                model_name=self.workflow.model_name,
            )
            
            # 429エラーが発生した場合、APIキーを切り替える
            if is_429_error:
                if self.api_key_manager.switch_to_next_key():
                    client = self.api_key_manager.create_client()
                    print(f"🔑 クライアント切り替え完了。次のファイルから新しいキーを使用します。\n")
            
            # 解析失敗またはis_valid = false の場合
            if not result or not result.get("is_valid", False):
                print(f"!! スキップ: {pdf_path.name} - 有効な解析結果が得られませんでした。")
                move_to_failed_dir(pdf_path, self.workflow.failed_dir)
                skipped_count += 1
                continue
            
            all_analysis_results.append(result)
        
        if not all_analysis_results:
            print("処理を続行するための有効な解析結果が得られませんでした。")
            return []
        
        # ステップ2: group_id でグループ化
        grouped_results: Dict[str, List[Dict[str, Any]]] = {}
        for result in all_analysis_results:
            group_id = result["group_id"]
            grouped_results.setdefault(group_id, []).append(result)
        
        print(f"--- 解析結果を {len(grouped_results)} グループに分類しました ---\n")
        
        # ステップ3: グループごとに結合・リネーム
        merged_count = 0
        for group_id, results in grouped_results.items():
            paths_to_combine = [r["original_path"] for r in results]
            
            try:
                # グループの代表ファイル（最初の解析結果）を取得
                first_result = results[0]
                staff_code = first_result.get('staff_code', '').strip()
                chassis_number = first_result.get('chassis_number', '').strip()
                customer_name = first_result.get('customer_name', '').strip()
                
                # ファイル名・フォルダ名の決定ロジック
                if chassis_number:
                    dir_name = chassis_number.replace('#', '')
                    base_filename = f"{staff_code}_{chassis_number}"
                elif customer_name:
                    dir_name = customer_name
                    base_filename = f"{staff_code}_{customer_name}"
                else:
                    print(f"!! 警告: グループID {group_id} のファイル名に必要なデータが不足しているため、スキップします。")
                    continue
                
                # フォルダ・ファイルのサニタイズ
                sanitized_dir_name = sanitize_filename(dir_name)
                sanitized_filename = sanitize_filename(base_filename)
                
                # 出力ディレクトリの作成
                output_sub_dir = self.workflow.output_dir / sanitized_dir_name
                ensure_dir_exists(output_sub_dir)
                output_path = output_sub_dir / f"{sanitized_filename}.pdf"
                
                print(f"[グループ処理] ID: {group_id} / ファイル数: {len(paths_to_combine)} / フォルダ: {sanitized_dir_name} / 出力名: {output_path.name}")
                
                # pypdfで結合
                success = combine_pdfs(paths_to_combine, output_path)
                if success:
                    output_paths.append({"path": output_path, "result": first_result})
                    merged_count += 1
                print()
                
            except Exception as e:
                print(f"!! 致命的警告: グループID {group_id} の処理中に予期せぬエラーが発生しました: {e}\n")
        
        print(f"--- PDF処理完了 ---")
        print(f"結合成功: {merged_count}件 / スキップ: {skipped_count}件\n")
        
        return output_paths
    
    def _send_emails(self, output_paths: List[Path]) -> None:
        """
        処理されたファイルをメール送信する。
        チャンク分割は chunk_size に従う。
        メール送信不要なワークフローの場合はスキップ。
        
        Args:
            output_paths: 送信対象のファイルパスと結果を含む辞書のリスト
        """
        # メール送信が不要なワークフローの場合（get_email_config が None を返す場合）
        email_config = self.workflow.get_email_config()
        if email_config is None:
            print("メール送信は対象外のワークフローです。スキップします。\n")
            return
        
        if not output_paths:
            print("メール送信対象のファイルがありません。\n")
            return
        
        if not self.sender_email or not self.sender_password:
            print("警告: メール送信に必要な環境変数が設定されていません。")
            print("メール送信をスキップします。\n")
            return
        
        print(f"--- メール送信開始 ---")
        
        # ファイルをチャンクに分割
        chunks = [
            output_paths[i : i + self.chunk_size]
            for i in range(0, len(output_paths), self.chunk_size)
        ]
        total_chunks = len(chunks)
        
        # 各チャンクごとにメール送信
        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_info = {"current": chunk_index, "total": total_chunks}
            
            # メール件名生成のためのデータ準備
            # チャンク内の最初のファイル（または単一ファイル）の結果を使用
            subject_data = chunk[0]["result"] if chunk else {}
            email_subject = self.workflow.get_email_subject(subject_data, chunk_info)
            
            email_body = self.workflow.get_email_body()

            # 添付ファイルのリストをPathオブジェクトのリストに変換
            attached_files = [item["path"] for item in chunk]
            
            success = send_email(
                self.sender_email,
                self.sender_password,
                self.recipient_email,
                email_subject,
                email_body,
                attached_files,
            )
            
            if success:
                print(f"メール {chunk_index}/{total_chunks} 送信完了\n")
            else:
                print(f"メール {chunk_index}/{total_chunks} 送信失敗\n")


# =============================================================================
# コマンドラインインターフェース
# =============================================================================

def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパースする。"""
    parser = argparse.ArgumentParser(
        description="統合請求書処理システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
利用可能なワークフロー:
  {', '.join(list_workflows())}

使用例:
  python main_processor.py maintenance    # メンテナンス処理を実行
  python main_processor.py warranty       # WARRANTY処理を実行
        """,
    )
    
    parser.add_argument(
        "workflow",
        nargs="?",
        default=None,
        help="実行するワークフロー名",
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="利用可能なワークフロー一覧を表示",
    )
    
    return parser.parse_args()


def main():
    """メインエントリポイント。"""
    args = parse_args()
    
    # ワークフロー一覧表示オプション
    if args.list:
        print(f"利用可能なワークフロー: {', '.join(list_workflows())}")
        sys.exit(0)
    
    # ワークフロー名が未指定の場合
    if not args.workflow:
        print("エラー: ワークフロー名を指定してください")
        print(f"利用可能なワークフロー: {', '.join(list_workflows())}")
        print(f"\n使用例: python main_processor.py maintenance")
        sys.exit(1)
    
    # ワークフロー実行
    try:
        engine = WorkflowEngine(args.workflow)
        engine.run()
    except ValueError as e:
        print(f"エラー: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n処理をキャンセルしました。")
        sys.exit(0)
    except Exception as e:
        print(f"\n予期せぬエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
