# 地震情報

気象庁の地震情報を取得し、`data.json` に保存してGitへ自動commit・pushする地震監視ページです。

## 構成

- `index.html` — GitHub Pagesで表示する地震情報ページ
- `data.json` — 最新30件の地震情報
- `monitor.py` — 気象庁の地震情報XMLを監視し、更新時だけcommit/push

## 監視方式

GitHub Actionsは使用しません。

`monitor.py` を常時動作させるPCで実行します。61秒ごとに気象庁の高頻度（地震火山）XMLフィードを確認し、新しい「震源・震度に関する情報」を見つけたときだけ `data.json` を更新して、次のGit操作を行います。

```text
気象庁
  ↓
https://www.data.jma.go.jp/developer/xml/feed/eqvol.xml
  ↓
monitor.py
  ↓
<entry> の title = 「震源・震度に関する情報」
  ↓
<link type="application/xml" href="...">
  ↓
個別JMAXML
  ↓
data.json
  ↓
git commit
  ↓
git push
  ↓
GitHub Pages
```

個別の地震XMLは `<link>` の `href` を使用して取得します。`eqvol.xml` には降灰予報など他の情報も含まれますが、地震監視では「震源・震度に関する情報」のentryだけを対象にします。

GitHubへの認証情報はスクリプトに保存せず、PC側のGit認証を使用します。

## 注意

気象庁の公開情報は随時更新されます。地震情報がまだ発表されていない項目は推測せず、`未確認` として扱います。

気象庁の地震情報カタログでは、震源・震度に関する情報（VXSE53）が随時提供される情報として案内されています。
