# ADR-0008: `count.select`に`kind`を追加する

* ステータス: 承認済み

## 決定

`count`ルールの`select`に`kind`プロパティを追加します。

追加後の`count`は、次のような形を取れます。

```yaml
- type: count
  select:
    path_regex: '.*\.key'
    kind: file
  maximum: 0
```

`select`内の条件はAND結合として扱います。
つまり、`path_regex`と`kind`の両方を満たすエントリだけが件数の対象になります。

初期拡張後の`count.select`では、次のプロパティを許可します。

* `path_regex`
* `kind`

## 理由

`count`は件数条件を表現するルールとして有用ですが、`select.path_regex`だけでは対象集合の絞り込みが不十分です。
特に、既存の`require`や`forbid`が持っている「パス条件 + kind条件」という表現を、そのまま`count`へ移せません。

たとえば、次のルールは現状の`require` / `forbid`では表現できます。

```yaml
- type: require
  path_regex: 'logs/[0-9]{8}\.log'
  kind: file
```

```yaml
- type: forbid
  path_regex: '.*\.key'
  kind: file
```

`count.select`に`kind`を追加し、`select`の条件をAND結合にすれば、これらは次のように表現できます。

```yaml
- type: count
  select:
    path_regex: 'logs/[0-9]{8}\.log'
    kind: file
  minimum: 1
```

```yaml
- type: count
  select:
    path_regex: '.*\.key'
    kind: file
  maximum: 0
```

この拡張により、`count`は件数条件だけでなく、`path_regex`を使う`require` / `forbid`と同等以上の表現力を持てるようになります。
将来的には、これらを`count`ベースの糖衣構文として整理する余地も生まれます。

また、`select`内の条件の結合方法としてはAND結合を採用します。
AND結合であれば、各条件が対象集合を絞り込む役割を持つため、仕様と実装が単純です。
一方、OR結合を早い段階で導入すると、`select`が条件木に近づき、件数ルールの導入よりも条件言語の設計が中心課題になります。

## 検討したが採用しなかった案

### `select`は`path_regex`のみのままにする案

この案では、`count`の仕様はより小さく保てます。
しかし、実用上は「どの種別のエントリを数えるのか」を指定したくなる場面がすぐに現れます。

また、`path_regex`を使う`require` / `forbid`との役割分担も曖昧なままになります。
今回は、`count`をより中核的な集合ルールとして育てるために、`kind`を追加します。

### `select`をOR結合にする案

OR結合があれば、「AまたはBに一致するものを数える」といった表現はしやすくなります。
しかし、OR結合を許可すると`select.any`や`select.all`のような条件構造が欲しくなり、設計が一段複雑になります。

現段階では、AND結合だけで十分に有用であり、仕様も簡潔に保てます。
OR結合は、将来必要性が明確になった時点で別途検討します。

## 影響

`count`は、`path_regex`に加えて`kind`でも対象集合を絞り込めるようになります。
これにより、件数条件の表現力が増し、既存の`require` / `forbid`の一部を`count`で統一的に表現できるようになります。

一方で、`count`は単なる件数ルールから、より一般的な集合ルールへ一歩進むことになります。
そのため、今後`select`に新しい条件を追加する際は、AND結合の単純さを損なわないかを意識して設計する必要があります。
