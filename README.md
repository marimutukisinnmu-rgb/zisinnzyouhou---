# 地震情報

気象庁の地震情報を取得し、`data.json` に保存してGitへ自動commit・pushする地震監視ページです。

## 構成

- `index.html` — GitHub Pagesで表示する地震情報ページ
- `data.json` — 最新30件の地震情報
- `monitor.py` — 気象庁の地震情報XMLを監視し、更新時だけcommit/push

## 監視方式

GitHub Actionsは使用しません。

`monitor.py` を常時動作させるPCで実行します。10秒ごとに気象庁の地震・火山XMLフィードを確認し、新しい「震源・震度に関する情報」を見つけたときだけ `data.json` を更新して、次のGit操作を行います。

```text
気象庁
  ↓
monitor.py
  ↓
data.json
  ↓
git commit
  ↓
git push
  ↓
GitHub Pages
```

GitHubへの認証情報はスクリプトに保存せず、PC側のGit認証を使用します。

## 注意

気象庁の公開情報は随時更新されます。地震情報がまだ発表されていない項目は推測せず、`未確認` として扱います。

気象庁の地震情報カタログでは、震源・震度に関する情報（VXSE53）が随時提供される情報として案内されています。
