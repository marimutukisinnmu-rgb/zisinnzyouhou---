# 地震情報

気象庁の地震情報を取得し、`data.json` に保存してGitへ自動commit・pushする地震監視ページです。

## 構成

- `index.html` — GitHub Pagesで表示する地震情報ページ
- `data.json` — 最新30件の地震情報
- `monitor.py` — 気象庁の地震情報XMLを監視し、更新時だけcommit/push
- `.github/workflows/monitor-fallback.yml` — `monitor.py` が停止した場合にGitHub Actionsから監視を補完

## 監視方式

通常は `monitor.py` を常時動作させるPCで実行します。

`monitor.py` は61秒ごとに気象庁の高頻度（地震火山）XMLフィードを確認し、新しい「震源・震度に関する情報」を見つけたときだけ `data.json` を更新して、Gitへcommit・pushします。

また、`monitor.py` のheartbeatが一定時間更新されていない場合は、GitHub Actionsの `monitor-fallback.yml` が5分ごとに起動し、監視を補完します。GitHub Actionsは通常の監視ではなく、`monitor.py` 停止時のフォールバックとして使用します。

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

monitor.py が停止
  ↓
GitHub Actions（monitor-fallback.yml）
  ↓
monitor.py --once
  ↓
data.json
```

個別の地震XMLは `<link>` の `href` を使用して取得します。`eqvol.xml` には降灰予報など他の情報も含まれますが、地震監視では「震源・震度に関する情報」のentryだけを対象にします。

## 出典

地震情報のデータ元は気象庁です。

- 気象庁 地震情報：https://www.jma.go.jp/bosai/map.html#contents=earthquake_map
- 気象庁 防災情報XML：https://www.data.jma.go.jp/developer/xml/feed/eqvol.xml

本ページでは、気象庁から取得した情報を処理・整形して表示しています。情報の加工・処理を行っているため、気象庁が本ページの情報を作成・提供しているものではありません。

## 認証

GitHubへの認証情報は `monitor.py` に保存せず、PC側のGit認証を使用します。

GitHub Actionsのフォールバックでは、リポジトリのSecretsに登録した認証情報を使用します。

## 注意

気象庁の公開情報は随時更新されます。地震情報がまだ発表されていない項目は推測せず、`未確認` として扱います。

気象庁の地震情報カタログでは、震源・震度に関する情報（VXSE53）が随時提供される情報として案内されています。
