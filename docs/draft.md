# 1. まず決めるべき全体方針

ファイルシステム向けスキーマでは、YAMLの設計で最初に効いてくるのは次の3点です。

## A. ルール中心にするか、ツリー中心にするか

2つの書き方があります。

### ルール中心

```yaml
rules:
  - require: README.md
  - require: src/
  - if_exists:
      path: secrets.enc
      then_require: secrets.key
```

### ツリー中心

```yaml
root:
  README.md:
    type: file
    required: true
  src:
    type: directory
    required: true
```

今回の用途だと、**ルール中心**が向いています。
理由は、あなたが挙げている要件が「木構造の定義」よりも「制約の列挙」に寄っているからです。

* このファイルが必要
* A があれば B も必要
* このディレクトリ配下はこの正規表現
* このファイルは 100 バイト以上

これはツリー定義より、ルールの並びの方が自然です。

## B. パス指定をどう表すか

ここは早めに決めるべきです。おすすめは以下です。

* すべて **スキーマ対象ルートからの相対パス**
* `/` 区切りで統一
* ディレクトリをパス末尾の `/` で表すのは**避ける**
* `kind: file|directory|symlink` を明示する

つまり、

```yaml
path: logs
kind: directory
```

のように書く方が安全です。
`logs/` という表記は人間には分かりやすいですが、実装で

* 正規化
* Windows風パス混入
* 末尾スラッシュ有無の比較

が面倒になります。

## C. 「対象の選択」と「制約」を分ける

これがとても重要です。

たとえば「logs 以下のファイル名が regex に一致する」は、実は2段階です。

1. 対象を選ぶ

   * `under: logs`
   * `kind: file`
2. 制約を課す

   * `name_regex: ...`

この分離を意識しておくと、後でルールの再利用がしやすいです。

# 2. おすすめのトップレベル構造

まずはこれくらいが扱いやすいです。

```yaml
version: 0

options:
  case_sensitive: true
  follow_symlinks: false

rules:
  - id: require-readme
    type: require
    path: README.md
    kind: file

  - id: require-src
    type: require
    path: src
    kind: directory
```

## 各トップレベルキーの役割

### `version`

将来スキーマ形式を変えたくなったときのために必須に近いです。

### `options`

全体の評価方針です。最初から全部はいりませんが、枠は用意しておくとよいです。

候補:

* `case_sensitive`
* `follow_symlinks`
* `allow_hidden_files`
* `path_separator_policy`
* `regex_engine_notes` など

### `rules`

ルール列です。基本はこれが主役です。

### `id`

必須推奨です。
エラー時に「どのルールに違反したか」を出しやすくなります。

# 3. ルール設計の基本形

ルールはできるだけ、次のどちらかの形に寄せるとよいです。

## 形1: 単一パスに対するルール

```yaml
- id: readme-required
  type: require
  path: README.md
  kind: file
```

## 形2: 複数エントリを対象にしたルール

```yaml
- id: logs-name-rule
  type: for_each
  select:
    under: logs
    kind: file
  assert:
    name_regex: '^[0-9]{8}\.log$'
```

この「単一対象ルール」と「集合対象ルール」を明確に分けると、かなり設計が安定します。

# 4. まず揃えるべきルール群

最初のバージョンで入れるべきものを、実装容易性と有用性のバランスで選ぶと次のあたりです。

## 4.1 存在必須: `require`

```yaml
- id: require-readme
  type: require
  path: README.md
  kind: file
```

意味:

* `README.md` が存在しなければ違反
* 存在しても kind が違えば違反

### 拡張候補

```yaml
- id: require-config-dir
  type: require
  path: config
  kind: directory
```

`kind` を省略可にする案もありますが、**省略不可の方が曖昧さが減ります**。
最初は明示必須の方が設計が締まります。

## 4.2 存在禁止: `forbid`

```yaml
- id: no-private-key
  type: forbid
  path: private.key
```

または

```yaml
- id: no-git-dir
  type: forbid
  path: .git
  kind: directory
```

これは `require` と対になる基本ルールです。

## 4.3 条件付き依存: `implies`

```yaml
- id: encrypted-secret-requires-key
  type: implies
  if:
    path: secrets.enc
    exists: true
  then:
    path: secrets.key
    exists: true
```

この形が一番素直です。
より簡略な記法もできますが、将来拡張しやすいのはこの形です。

### さらに一般化した形

```yaml
- id: local-config-requires-base-config
  type: implies
  if:
    path: config.local.yaml
    exists: true
  then:
    path: config.yaml
    exists: true
```

将来は `if` 側にサイズや kind 条件も載せられます。

## 4.4 相互排他: `xor` / `mutually_exclusive`

実務だとかなり便利です。

```yaml
- id: choose-one-config
  type: mutually_exclusive
  paths:
    - config.json
    - config.yaml
```

意味:

* 両方存在してはいけない

あるいは「ちょうど1つ必須」までやりたいなら

```yaml
- id: exactly-one-config
  type: count
  select:
    paths:
      - config.json
      - config.yaml
  min: 1
  max: 1
```

このように count 系に寄せる設計も可能です。

## 4.5 属性制約: `stat`

単一ファイルのサイズなどは、専用ルールより `stat` にまとめるのがきれいです。

```yaml
- id: data-bin-size
  type: stat
  path: data.bin
  kind: file
  constraints:
    min_bytes: 100
```

拡張しやすいです。

```yaml
- id: image-size-range
  type: stat
  path: assets/logo.png
  kind: file
  constraints:
    min_bytes: 1024
    max_bytes: 1048576
```

将来候補:

* `min_bytes`
* `max_bytes`
* `non_empty: true`
* `mode`
* `mtime_after`
* `mtime_before`

## 4.6 集合ルール: `for_each`

これが重要です。
「このディレクトリ以下の全ファイル名は〜」のような条件の中心になります。

```yaml
- id: logs-file-names
  type: for_each
  select:
    under: logs
    recursive: true
    kind: file
  assert:
    name_regex: '^[0-9]{8}\.log$'
```

### 良い点

* `select` と `assert` が分かれている
* ほかの制約にも使い回せる
* Python実装も分かりやすい

### assert 側の候補

```yaml
assert:
  name_regex: '^[0-9]{8}\.log$'
  min_bytes: 1
```

あるいは複数条件対応で

```yaml
assert:
  all:
    - name_regex: '^[0-9]{8}\.log$'
    - min_bytes: 1
```

まで拡張できます。

## 4.7 件数制約: `count`

これも便利です。

```yaml
- id: at-least-one-log
  type: count
  select:
    under: logs
    recursive: true
    kind: file
    name_regex: '^[0-9]{8}\.log$'
  min: 1
```

```yaml
- id: no-more-than-10-checkpoints
  type: count
  select:
    under: checkpoints
    recursive: false
    kind: file
  max: 10
```

`count` は「存在ルールの一般化」として使えます。

# 5. `select` の設計をちゃんと決める

集合ルールの核になるので、`select` はかなり重要です。
おすすめは次のような構造です。

```yaml
select:
  under: logs
  recursive: true
  kind: file
  name_regex: '^[^.].*'
```

候補フィールドはこれくらい。

* `under`: このディレクトリ配下
* `recursive`: 再帰するか
* `kind`: `file|directory|symlink`
* `name_regex`: basename に対する条件
* `path_regex`: 相対パス全体に対する条件
* `paths`: 明示列挙
* `exists`: これは select には不要かも

### `name_regex` と `path_regex` は分ける

これは分けた方が絶対に良いです。

* `name_regex`: `basename`
* `path_regex`: ルート相対パス全体

例:

```yaml
name_regex: '^[0-9]{8}\.log$'
```

と

```yaml
path_regex: '^logs/[0-9]{4}/.*\.log$'
```

は意味が違います。

# 6. `assert` の設計案

`for_each` の `assert` は、小さな条件言語にすると拡張しやすいです。

最初の段階では、フラットな形でもよいです。

```yaml
assert:
  name_regex: '^[0-9]{8}\.log$'
  min_bytes: 100
```

ただし、将来的に OR 条件や NOT 条件が欲しくなるなら、最初から論理演算ノードを意識してもよいです。

```yaml
assert:
  all:
    - field: name
      matches: '^[0-9]{8}\.log$'
    - field: size
      gte: 100
```

これは汎用的ですが、書くのが少し重いです。

今回の用途なら、**最初はドメイン専用キー型**の方がよいです。

```yaml
assert:
  name_regex: '^[0-9]{8}\.log$'
  min_bytes: 100
```

そして将来必要になったら

```yaml
assert:
  any:
    - extension_in: [.jpg, .png]
    - name_regex: '^README'
```

のように拡張する方が現実的です。

# 7. 単一対象と集合対象で共通化できる属性

評価器を作るときのことを考えると、次の属性は共通に扱えると楽です。

* `exists`
* `kind`
* `name`
* `path`
* `size`
* `extension`

たとえば `stat` だけでなく `if` 条件にも載せられるようにしておくと一貫します。

```yaml
- id: big-file-requires-metadata
  type: implies
  if:
    path: data.bin
    kind: file
    min_bytes: 1048576
  then:
    path: data.meta
    exists: true
```

この設計はきれいですが、最初からここまで一般化しすぎると実装が重くなります。
初版では `if.path exists` 程度に限定でも十分です。

# 8. 推奨する最小スキーマ案

初版としてかなりバランスが良いのは、次のセットです。

```yaml
version: 0

options:
  case_sensitive: true
  follow_symlinks: false

rules:
  - id: require-readme
    type: require
    path: README.md
    kind: file

  - id: require-src-dir
    type: require
    path: src
    kind: directory

  - id: no-private-key
    type: forbid
    path: private.key
    kind: file

  - id: encrypted-secret-requires-key
    type: implies
    if:
      path: secrets.enc
      exists: true
    then:
      path: secrets.key
      exists: true

  - id: logs-filename-format
    type: for_each
    select:
      under: logs
      recursive: true
      kind: file
    assert:
      name_regex: '^[0-9]{8}\.log$'

  - id: data-min-size
    type: stat
    path: data.bin
    kind: file
    constraints:
      min_bytes: 100

  - id: at-least-one-log-file
    type: count
    select:
      under: logs
      recursive: true
      kind: file
      name_regex: '^[0-9]{8}\.log$'
    min: 1
```

これはかなり実用になります。

# 9. 書き味をよくするための命名規則

YAML DSL は、機能より命名で使いやすさが変わります。
おすすめは以下です。

## 動詞ベースの `type`

* `require`
* `forbid`
* `implies`
* `for_each`
* `count`
* `stat`

理解しやすいです。

## サイズは `bytes` に統一

* `min_bytes`
* `max_bytes`

`size`, `min_size`, `minimum_size` が混在するとつらいです。

## 正規表現系は `*_regex`

* `name_regex`
* `path_regex`

## ディレクトリ配下指定は `under`

`in`, `within`, `base_dir` より分かりやすいです。

# 10. 迷いやすい論点とおすすめ

## 10.1 ファイル内容まで扱うか

初版では**扱わない方がよい**です。
たとえば

* JSONとして妥当
* 文字列を含む
* 行数
* ハッシュ

などは魅力的ですが、別フェーズに分けた方がスキーマが綺麗です。

やるなら後で `content` 系ルールを足すのがおすすめです。

```yaml
- id: package-json-valid
  type: content
  path: package.json
  format: json
```

## 10.2 glob を入れるか

`regex` と `glob` の両方を入れると混乱しがちです。
初版ではどちらか一方でよく、私は**regex寄り**をおすすめします。

理由:

* 実装が単純
* 曖昧さが少ない
* basename/path の区別がしやすい

ただし、ユーザー体験としては glob の方が優しいので、将来は

* `name_glob`
* `path_glob`

を追加してもよいです。

## 10.3 空ディレクトリの扱い

`for_each` は対象が0件でも成功するのか、という論点があります。
これは重要です。

おすすめは:

* `for_each` は **0件なら成功**
* 必要なら `count` を別途書く

つまり

```yaml
- type: for_each
  ...
```

は「対象があればそれら全てが条件を満たす」であり、

```yaml
- type: count
  min: 1
```

で存在数を担保する、という役割分担です。

これは非常に分かりやすいです。

## 10.4 正規表現の対象は full match か partial match か

ここは仕様に明記すべきです。
おすすめは **full match 相当** にすることです。

つまり `'^[0-9]{8}\.log$'` を期待する設計。
Python実装では `re.fullmatch` を使う方が事故が少ないです。

## 10.5 シンボリックリンク

最初に少しだけ方針を決めておくと後が楽です。

おすすめ:

* 初版では `kind: symlink` を認識する
* ただし `follow_symlinks: false` をデフォルト
* 追跡先まで検査しない

これで十分です。

# 11. エラー出力を前提にしたスキーマ設計

あとで使いやすくするには、YAML自体にエラーメッセージ補助を持たせてもよいです。

```yaml
- id: require-readme
  type: require
  path: README.md
  kind: file
  message: README.md が必要です
```

必須ではありませんが、将来CIで使うときに便利です。

ほかに `severity` を持たせる案もあります。

```yaml
- id: large-file-warning
  type: stat
  path: dump.bin
  constraints:
    max_bytes: 10485760
  severity: warning
```

これも初版ではなくてもよいですが、拡張余地として良いです。

# 12. 将来拡張しやすい方向

今の段階で見据えておくとよい拡張は次です。

## 12.1 論理合成

```yaml
- type: any_of
  rules:
    - type: require
      path: config.yaml
      kind: file
    - type: require
      path: config.json
      kind: file
```

## 12.2 内容検査

```yaml
- type: content
  path: metadata.json
  format: json
  json_schema: ...
```

## 12.3 ハッシュや拡張子制約

```yaml
assert:
  extension_in: [.jpg, .png]
```

## 12.4 ディレクトリ構造の再利用

アンカーや include 的な仕組みが欲しくなることがありますが、初版では不要です。

# 13. 私ならこうまとめる

初版の設計思想としてはこうです。

## スキーマの哲学

* ルール列挙型
* パスはすべてルート相対
* 対象選択と制約を分離
* 単一対象ルールと集合対象ルールを分ける
* 空集合の扱いは count に任せる
* サイズ単位は bytes に統一
* 正規表現は full match 前提

## 初版で採用するルール型

* `require`
* `forbid`
* `implies`
* `stat`
* `for_each`
* `count`

この6個あればかなり戦えます。

# 14. 初版仕様のたたき台

最後に、かなりそのまま仕様書の骨子にできる形で置きます。

```yaml
version: 0

options:
  case_sensitive: true
  follow_symlinks: false

rules:
  - id: string
    type: require | forbid | implies | stat | for_each | count
    ...
```

## `require`

```yaml
- id: require-readme
  type: require
  path: README.md
  kind: file
```

## `forbid`

```yaml
- id: forbid-private-key
  type: forbid
  path: private.key
  kind: file
```

## `implies`

```yaml
- id: secret-needs-key
  type: implies
  if:
    path: secrets.enc
    exists: true
  then:
    path: secrets.key
    exists: true
```

## `stat`

```yaml
- id: data-size
  type: stat
  path: data.bin
  kind: file
  constraints:
    min_bytes: 100
    max_bytes: 1000000
```

## `for_each`

```yaml
- id: logs-rule
  type: for_each
  select:
    under: logs
    recursive: true
    kind: file
  assert:
    name_regex: '^[0-9]{8}\.log$'
```

## `count`

```yaml
- id: at-least-one-log
  type: count
  select:
    under: logs
    recursive: true
    kind: file
    name_regex: '^[0-9]{8}\.log$'
  min: 1
  max: 100
```
