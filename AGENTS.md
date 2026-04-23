# AGENTS.md

このファイルは、このリポジトリで作業するエージェント向けの補足指示です。

## リポジトリ概要

* プロジェクト名: `fs-schema`
* 目的: ファイルおよびディレクトリ構造を検証するための「FS Schema」（File System Schema）を扱うライブラリ
* ツールセット:
  * Python: v3.12.11
  * ツール管理: `mise`
  * パッケージ管理: `uv`

## 作業方針

* 既存の設計や命名に合わせ、変更は必要最小限に留めてください
* ユーザが作成した可能性のある未関連変更は巻き戻さないでください
* 仕様が曖昧な場合はREADMEや既存コードから意図を確認してから変更してください

## 実装・検証

* 依存関係や仮想環境の操作は`uv`を優先してください
* Pythonを実行する場合は`uv run`を優先してください
* 変更後は、必要に応じて関連するテストや静的検証を実行してください

```sh
uv run pytest
uv run ruff check --fix
uv run ruff format
uv run ty check
```

## コミット

バージョン管理システムにおけるコミットについては`docs/rules/commit.md`を参照してください。

## ドキュメンテーション

自然言語によるドキュメンテーション（ソースコード中のコメント、エラーメッセージなども含む）については`docs/rules/documentation.md`を参照してください。

## ADR（Architecture Decision Record）

ADRについては`docs/adr`を参照してください。
