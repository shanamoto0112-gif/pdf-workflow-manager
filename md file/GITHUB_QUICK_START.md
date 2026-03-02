# GitHub アップロード - クイックスタート（5分版）

## 🚀 最速手順

### 1️⃣ GitHub でリポジトリを作成（2分）

```
GitHub.com にログイン
→ "New repository" をクリック
→ Repository name: pdf-workflow-manager
→ "Public" を選択
→ "Create repository" をクリック
→ リモート URL をコピー（例：https://github.com/your-username/pdf-workflow-manager.git）
```

---

### 2️⃣ ローカルでセットアップ（3分）

```bash
# プロジェクトディレクトリで実行
cd /path/to/pdf-workflow-manager

# Git を初期化
git init

# リモートを登録（コピーした URL を使用）
git remote add origin https://github.com/your-username/pdf-workflow-manager.git

# ブランチ名を main に変更
git branch -M main

# ファイルをステージング
git add .

# コミット
git commit -m "Initial commit: PDF Workflow Manager v1.0"

# GitHub にプッシュ
git push -u origin main
```

---

### 3️⃣ 完了！ ✅

```
https://github.com/your-username/pdf-workflow-manager
```

にアクセスして確認！

---

## 📝 重要：config.env について

**.gitignore で除外する必要があります！**

```bash
# プロジェクトディレクトリで実行
echo "config.env" >> .gitignore
echo "!config.env.example" >> .gitignore

git add .gitignore
git commit -m "chore: Update .gitignore"
git push origin main
```

---

## ✨ これだけ！

以上で GitHub へのアップロードが完了です！ 🎉

詳細は `GITHUB_UPLOAD_GUIDE.md` を参照してください。

---

**Happy GitHub! 🚀**
