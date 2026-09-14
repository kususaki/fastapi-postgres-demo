# FastAPI PostgreSQL Demo

このリポジトリは、以下の会話をもとに作成しました。

- 元の会話: https://chatgpt.com/share/6a94d0cb-e58c-83e8-96c3-8c5c622c78de

このアプリは、弁当の仕出し注文を題材にした業務用デモアプリです。

**FastAPI + PostgreSQL + HTML/Jinja2** というシンプルな構成で、画面はクラスレスCSSの Pico.css と HTMX で組み立てており、RDBにおける1対多・多対多の関係と、Webアプリケーションからのデータ登録・取得を確認することを目的とします。

現在の実装では、**会社を選択して弁当を数量指定し、注文を登録する**ところまでを一連の画面として実装しています。また、登録した注文の履歴と、個別の注文完了画面、注文元会社の連絡先を確認する取引先一覧画面も提供しています。

> このデモの目的は、業務上のデータをどのようにRDBで表現し、FastAPIからSQLとPydanticモデルを通じて扱うかを、わかりやすい具体例として学ぶことです。会社・注文・弁当・アレルゲンの関係を、実際のWebフォームとデータベース処理を通じて確認できます。

---

## 1. システム構成

```mermaid
flowchart LR
    B[Browser]
    F[FastAPI]
    P[(PostgreSQL)]

    B -->|HTTP GET / POST| F
    F -->|SQL| P
```

使用技術：

- Python
- FastAPI
- Uvicorn
- psycopg
- PostgreSQL
- Pydantic
- Jinja2
- Pico.css（クラスレスCSSフレームワーク / CDN）
- HTMX（CDN）

フロントエンドは**HTML/Jinja2を中心としたシンプルな構成**です。

ReactやVueなどのフロントエンドフレームワークは使用していません。

Pico.css と HTMX はどちらも CDN から `<link>` / `<script>` 1行で読み込むだけで、
npm もビルドツールも不要です。

- **Pico.css** は、`<article>` `<nav>` `<table>` `<form>` `<details>` といった
  セマンティックなHTMLを書くだけで見栄えが整う「クラスレス」CSSです。
  以前はテンプレート4ファイルに**944行のCSS**が直接書かれており、
  このリポジトリの本題であるSQL・Pydantic・Jinja2の対応関係を埋もれさせていました。
  現在テンプレートに残っている自前のCSSは、日本語フォントを指定する
  `--pico-font-family` の**1行だけ**です。
- **HTMX** は、`hx-get` / `hx-post` といったHTML属性だけで
  「サーバーが返したHTMLの一部を差し替える」ことを行うライブラリです。
  仮想DOMもコンポーネントモデルも持ち込みません。
  これにより**手書きのJavaScriptは0行**になり、
  金額計算はPython側（`OrderItem` と `format_yen`）に一本化されました。

---

## 2. PostgreSQL

デフォルトの接続先は `demo_db` です。

`db.py` では、環境変数 `DATABASE_URL` が設定されている場合はそれを使用し、設定されていない場合は以下を使用します。

```text
dbname=demo_db
```

接続確認：

```bash
psql demo_db
```

本番環境などでは、例えば `DATABASE_URL` を設定して接続先を切り替えられます。

---

## 3. ディレクトリ構成

現在のPythonコードから確認できるアプリケーション構成は次のとおりです。

```text
fastapi-postgres-demo/
├── app/
│   ├── main.py
│   ├── db.py
│   ├── schemas.py
│   └── templates/
│       ├── base.html            # 全ページ共通のレイアウト（継承元）
│       ├── index.html
│       ├── companies.html
│       ├── order_history.html
│       ├── order_complete.html
│       ├── _summary.html        # 注文概要パネル（部分テンプレート）
│       └── _company_rows.html   # 取引先カード（部分テンプレート）
├── tests/
│   └── test_orders_complete.py
├── .github/
│   └── workflows/
│       └── ci.yml          # CI（pre-commit と同じチェックを実行）
├── .pre-commit-config.yaml # チェック項目の唯一の定義
├── pyproject.toml          # 依存関係 + ruff / mypy / pytest の設定
├── uv.lock
├── .venv/
├── .gitignore
└── ...
```

`main.py` では `app/templates` をJinja2のテンプレートディレクトリとして使用しています。

各画面のテンプレートは `{% extends "base.html" %}` で共通レイアウトを継承します。
`<head>`・CDNの読み込み・ナビゲーションは `base.html` だけが持ちます。

先頭が `_` のファイルは**部分テンプレート**です。
完全なHTML文書ではなく画面の一部だけを出力し、
通常のページ（`{% include %}`）とHTMXが呼ぶRoute（`_summary.html` は
`POST /orders/summary`、`_company_rows.html` は `GET /companies/rows`）の
両方から同じものを使い回します。

---

## 4. データベーススキーマ

現在のアプリケーションで利用している主要なテーブルは以下です。

```mermaid
erDiagram
    companies ||--o{ orders : places
    orders ||--o{ order_items : contains
    bento ||--o{ order_items : ordered
    bento ||--o{ bento_allergens : has
    allergens ||--o{ bento_allergens : applies

    companies {
        bigint id PK
        varchar name
        varchar contact_name
        varchar email
        varchar phone
    }
    orders {
        bigint id PK
        bigint company_id FK
        date order_date
        timestamp created_at
    }

    order_items {
        bigint order_id PK,FK
        bigint bento_id PK,FK
        integer quantity
    }

    bento {
        bigint id PK
        varchar name
        integer price
    }

    allergens {
        bigint id PK
        varchar name
    }
    bento_allergens {
        bigint bento_id PK,FK
        bigint allergen_id PK,FK
    }
```

### 4.1 `companies`

注文元の会社を管理します。

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | 会社ID |
| `name` | VARCHAR(200) | NOT NULL | 会社名 |
| `contact_name` | VARCHAR(100) | | 担当者名 |
| `email` | VARCHAR(255) | | メールアドレス |
| `phone` | VARCHAR(50) | | 電話番号 |

注文画面では、会社選択欄に表示するために `id` と `name` を取得しています。

```sql
SELECT id, name
FROM companies
ORDER BY name;
```

取引先一覧画面（`GET /companies`）では、担当者・連絡先を含めて取得し、あわせて会社ごとの注文実績を集計します。

```sql
SELECT
    c.id,
    c.name,
    c.contact_name,
    c.email,
    c.phone,
    COUNT(DISTINCT o.id) AS order_count,
    MAX(o.order_date) AS last_order_date,
    COALESCE(SUM(b.price * oi.quantity), 0) AS total_price
FROM companies c
LEFT JOIN orders o
    ON o.company_id = c.id
LEFT JOIN order_items oi
    ON oi.order_id = o.id
LEFT JOIN bento b
    ON b.id = oi.bento_id
WHERE %(keyword)s = ''
    OR CONCAT_WS(' ', c.name, c.contact_name, c.email, c.phone)
        ILIKE %(pattern)s
GROUP BY c.id, c.name, c.contact_name, c.email, c.phone
ORDER BY c.name;
```

`WHERE` 句は取引先一覧のキーワード絞り込みに対応します。
キーワードが空文字なら `%(keyword)s = ''` が真になり、全件を返します。

- `ILIKE` はPostgreSQLの大文字小文字を区別しない部分一致です。
- `CONCAT_WS` はNULLの列を読み飛ばすため、`contact_name` などが未登録の会社も
  会社名で検索できます。
- キーワードは `%(keyword)s` / `%(pattern)s` という**名前付きプレースホルダ**で
  psycopgに渡します。SQL文字列に値を埋め込まないため、SQLインジェクションを防げます。

`contact_name`、`email`、`phone` はNULLを許容するため、Python側では `str | None` として扱い、未登録の場合は画面に「未登録」と表示します。

注文が1件もない会社も一覧に表示できるよう、`orders` 以降は `LEFT JOIN` で結合しています。

---

### 4.2 `orders`

1回の注文を管理します。

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | 注文ID |
| `company_id` | BIGINT | FK | 注文元会社 |
| `order_date` | DATE | NOT NULL | 注文日 |
| `created_at` | TIMESTAMP | NOT NULL | 登録日時 |

関係：

```mermaid
flowchart LR
    C[companies] -->|1 : N| O[orders]
```

1つの会社から複数の注文が発生します。

注文登録時には、`company_id`、`order_date`、`created_at` が登録されます。

`created_at` はSQL側で `NOW()` を使用して設定します。

---

### 4.3 `bento`

弁当マスタです。

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | 弁当ID |
| `name` | VARCHAR(200) | NOT NULL | 弁当名 |
| `price` | INTEGER | NOT NULL | 価格 |

現在のPythonコードでは、注文画面に表示するために `id`、`name`、`price` を取得しています。

```sql
SELECT id, name, price
FROM bento
ORDER BY id;
```

価格は注文履歴・注文詳細画面の合計金額計算にも使用されます。

---

### 4.4 `order_items`

1つの注文に含まれる弁当と数量を管理します。

| Column | Type | Constraint | Description |
|---|---|---|---|
| `order_id` | BIGINT | PK, FK | 注文ID |
| `bento_id` | BIGINT | PK, FK | 弁当ID |
| `quantity` | INTEGER | NOT NULL | 数量 |

複合主キー：

```text
PRIMARY KEY (order_id, bento_id)
```

関係：

```mermaid
flowchart LR
    O[orders] -->|N : N| B[bento]
    O --> OI[order_items]
    B --> OI
```

例えば、1つの注文に複数種類の弁当を含めることができます。

```text
注文ID 1
  ├── 唐揚げ弁当 × 10
  ├── 鮭弁当     × 5
  └── 幕の内弁当 × 3
```

注文登録時には、`orders` に注文ヘッダを登録した後、`order_items` に各弁当の数量を登録します。

---

### 4.5 `allergens`

アレルギー情報のマスタです。

| Column | Type | Constraint | Description |
|---|---|---|---|
| `id` | BIGSERIAL | PK | アレルギーID |
| `name` | VARCHAR(100) | NOT NULL, UNIQUE | アレルギー名 |

注文画面の食品アレルギー表で、弁当に含まれるアレルゲンの表示に利用しています。

---

### 4.6 `bento_allergens`

弁当とアレルギーの多対多関係を管理します。

| Column | Type | Constraint | Description |
|---|---|---|---|
| `bento_id` | BIGINT | PK, FK | 弁当ID |
| `allergen_id` | BIGINT | PK, FK | アレルギーID |

関係：

```mermaid
flowchart LR
    B[bento] -->|N : N| A[allergens]
    B --> BA[bento_allergens]
    A --> BA
```

例えば、次のような関係を表現できます。

```text
唐揚げ弁当
  ├── 小麦
  ├── 卵
  └── 大豆
```

注文画面の食品アレルギー表で、弁当とアレルギーの関係を取得するために利用しています。

---

## 5. アプリケーションのデータモデル

Python側では、Pydanticを利用してデータモデルを定義しています。

モデルは `frozen=True` としており、生成後に変更できないイミュータブルなモデルとして扱います。

### `Company`

```text
id: int
name: str
```

### `CompanyContact`

```text
id: int
name: str
contact_name: str | None
email: str | None
phone: str | None
order_count: int
last_order_date: str | None
total_price: int
```

取引先一覧画面で使用する、会社の連絡先と注文実績です。

### `Bento`

```text
id: int
name: str
price: int
```

`price` は0以上です。

### `OrderSummary`

```text
id: int
order_date: str
company_name: str
total_price: int
```

注文履歴・注文完了画面で使用する注文の概要です。

### `OrderItem`

```text
name: str
quantity: int
price: int
subtotal: int
```

注文に含まれる弁当1種類分の明細です。

### `QuantitySelection`

```text
bento_id: int
quantity: int
```

フォームから受け取った「弁当IDと数量」の組を表します。

### `OrderDraft`

```text
company_id: int
order_date: str
quantities: tuple[QuantitySelection, ...]
```

注文登録前のデータを表します。

---

# 6. API / Route

現在のFastAPIアプリケーションでは、以下のRouteを提供しています。

| Method | Path | 内容 |
|---|---|---|
| GET | `/` | 注文登録画面 |
| GET | `/companies` | 取引先一覧 |
| POST | `/orders` | 注文登録 |
| GET | `/orders` | 注文履歴 |
| GET | `/orders/complete` | 注文完了・注文詳細 |
| POST | `/orders/summary` | 注文概要パネル（HTMX用の部分HTML） |
| GET | `/companies/rows` | 取引先カード（HTMX用の部分HTML） |

下2つはHTMXが呼ぶRouteで、完全なHTML文書ではなく画面の一部だけを返します。

---

## 6.1 GET `/`

注文登録画面を表示します。

```http
GET /
```

FastAPIからテンプレートへ以下のデータを渡します。

```text
companies
bentos
bento_allergens
today
company_name / order_date / items / total_price
```

`companies` は会社選択欄、`bentos` は弁当と価格・数量入力欄の生成に利用します。
`bento_allergens` は `<details>` で開く食品アレルギー表に使います。

`today` は注文日欄の初期値です。以前はブラウザのJavaScriptで埋めていましたが、
サーバー側で `value="{{ today }}"` として渡すようになりました。

最後の4つは注文概要パネルの初期状態で、`_summary.html` がそのまま受け取ります。
つまり最初の描画と、あとからHTMXが差し替える内容は**まったく同じテンプレート**です。

ナビゲーションから `GET /companies` や `GET /orders` へ遷移できます。

---

## 6.2 GET `/companies`

取引先一覧画面を表示します。

```http
GET /companies
```

会社ごとに、

- 会社名
- 担当者名
- メールアドレス
- 電話番号
- 注文件数
- 最終注文日
- 累計金額

を表示します。

`companies.contact_name`、`companies.email`、`companies.phone` を利用する画面です。

メールアドレスは `mailto:`、電話番号は `tel:` リンクとして表示し、未登録の項目は「未登録」と表示します。

会社名・担当者・連絡先による絞り込みは、**サーバー側のSQL**で行います。
検索欄に入力するとHTMXが `GET /companies/rows` を呼び、返ってきた部分HTMLで
一覧を差し替えます（§6.8）。

---

## 6.3 POST `/orders`

注文を登録します。

```http
POST /orders
Content-Type: application/x-www-form-urlencoded
```

注文には、

- 注文元会社
- 注文日
- 1種類以上の弁当
- 各弁当の数量

が必要です。

### フォーム項目

```text
company_id
order_date
quantity_{bento.id}
```

例えば、

```text
company_id=1
order_date=2026-08-30
quantity_1=10
quantity_2=5
quantity_3=3
```

のようなフォームを受け取ります。

`quantity_N` の `N` は `bento.id` を表します。

FastAPI側では、`quantity_` を取り除いた文字列を整数に変換して弁当IDとして扱います。

数量が0以下の項目は注文対象から除外され、1つも正の数量が存在しない場合は400エラーになります。

---

## 6.4 注文登録の処理

注文登録は、注文ヘッダと注文明細を**同一トランザクション**で処理します。

```mermaid
flowchart TD
    A["POST /orders"] --> B["フォームを解析"]
    B --> C["OrderDraftを生成"]
    C --> D["INSERT orders"]
    D --> E["order_idを取得"]
    E --> F["INSERT order_items"]
    F --> G["COMMIT"]
    G --> H["303 Redirect"]
    H --> I["/orders/complete?order_id=..."]
```

`db.insert_order()` では、

1. `orders` に注文を登録
2. `RETURNING id` で注文IDを取得
3. `order_items` に各明細を登録
4. すべて成功したらコミット

という流れで処理します。

途中でエラーが発生した場合はトランザクション全体がロールバックされます。

したがって、

```text
orders
```

だけ登録されて、

```text
order_items
```

が登録されない状態を避ける設計になっています。

---

## 6.5 GET `/orders`

注文履歴を表示します。

```http
GET /orders
```

注文ごとに、

- 注文ID
- 注文日
- 会社名
- 合計金額

を取得します。

合計金額は、以下の関係からSQLで計算しています。

```text
bento.price × order_items.quantity
```

複数の明細がある場合は `SUM()` で合計します。

注文は、

```text
注文日 DESC
注文ID DESC
```

の順で表示されます。

---

## 6.6 GET `/orders/complete`

注文登録後の注文完了画面、および個別注文の詳細を表示します。

```http
GET /orders/complete?order_id=1
```

注文IDに対応する、

- 注文ID
- 注文日
- 会社名
- 合計金額
- 弁当名
- 数量
- 単価
- 小計

を取得します。

存在しない注文IDが指定された場合は `404 Not Found` を返します。

---

## 6.7 POST `/orders/summary`

注文登録画面の右側にある注文概要パネルだけを描画して返します。

```http
POST /orders/summary
```

注文フォームの入力が変わるたびに、HTMXがフォーム全体をこのRouteへPOSTし、
返ってきたHTMLで `<aside id="summary">` の中身を差し替えます。

```html
<aside id="summary"
       hx-post="/orders/summary"
       hx-trigger="input from:#order-form delay:200ms, change from:#order-form"
       hx-include="#order-form">
  {% include "_summary.html" %}
</aside>
```

HTMXの属性は `<form>` ではなく `<aside>` 側に置いている点が重要です。
`<form>` に付けるとHTMXがsubmitを横取りしてしまい、
`POST /orders` → 303リダイレクトという通常の遷移が壊れます。
`hx-include` でフォームの値を**読むだけ**にすれば干渉しません。

明細は注文完了画面と同じ `OrderItem` モデルを組み立てて描画します。
金額計算がプレビューと確定後で1箇所に揃うため、ずれようがありません。

`POST /orders` と違い、**弁当が1件も選ばれていなくても400にはなりません**。
概要パネルは空のフォームから始まるためです。
この違いのために、数量を取り出す処理は次の2つに分かれています。

| Function | 内容 |
|---|---|
| `iter_quantities(form)` | `quantity_*` から正の数量を取り出す（空でもよい） |
| `parse_quantities(form)` | `iter_quantities()` を呼び、空なら400を返す |

> 実運用であれば、入力のたびに弁当・会社マスタを引き直すのは避けて
> キャッシュするところです。ここでは教材として素直な実装を優先し、
> `delay:200ms` のデバウンスだけを入れています。

---

## 6.8 GET `/companies/rows`

取引先一覧のカード部分だけを描画して返します。

```http
GET /companies/rows?q=ABC
```

`q` はキーワードで、`db.fetch_company_contacts(keyword=q)` を通じて
SQLの `ILIKE` による絞り込みになります（§4.1）。

```html
<input type="search" name="q"
       hx-get="/companies/rows"
       hx-trigger="input changed delay:300ms, search"
       hx-target="#company-rows" />
<div id="company-rows">{% include "_company_rows.html" %}</div>
```

`HX-Request` ヘッダを見て全ページと部分HTMLを出し分ける方法もありますが、
このリポジトリでは**独立したRoute**にしています。
URLを直接開けば何が返るかを確認でき、そのままテストにも書けるためです。

---

# 7. 注文履歴のデータ取得

注文履歴では、`orders`、`companies`、`order_items`、`bento` をJOINして注文情報を取得します。

概念的には次のような関係です。

```mermaid
flowchart LR
    C[companies] --> O[orders]
    O --> OI[order_items]
    B[bento] --> OI
```

注文の合計金額は、

```sql
SUM(b.price * oi.quantity)
```

によって計算します。

注文詳細では、明細ごとに、

```sql
b.price * oi.quantity
```

を小計として取得します。

---

# 8. HTMLとDBの対応

注文登録画面では、HTMLのフォーム項目とデータベースの列を次のように対応させています。

| HTML | Python | PostgreSQL |
|---|---|---|
| 会社選択 | `company_id` | `companies.id` |
| 注文日 | `order_date` | `orders.order_date` |
| 弁当 | `bento.id` | `bento.id` |
| 弁当名 | `bento.name` | `bento.name` |
| 価格 | `bento.price` | `bento.price` |
| 数量 | `quantity_{bento.id}` | `order_items.quantity` |
| 注文 | `POST /orders` | `orders` |
| 注文明細 | `POST /orders` | `order_items` |

フォームは `<label>` で項目名と入力欄を包んだ素のHTMLです。
数量は `<input type="number" min="0">` で、増減ボタンは持ちません。
`name` 属性が `quantity_{bento.id}` である点は変わっておらず、
ここがHTMLとDBをつなぐ鍵になっています。

注文概要パネルは、同じ `name` をHTMXがそのままサーバーへ送り返し、
`iter_quantities()` が `quantity_` の接頭辞から `bento.id` を復元します。

取引先一覧画面では、次のように対応させています。

| HTML | Python | PostgreSQL |
|---|---|---|
| 会社名 | `company.name` | `companies.name` |
| 担当者 | `company.contact_name` | `companies.contact_name` |
| メール | `company.email` | `companies.email` |
| 電話 | `company.phone` | `companies.phone` |
| 注文件数 | `company.order_count` | `orders` の件数 |
| 最終注文日 | `company.last_order_date` | `MAX(orders.order_date)` |
| 累計金額 | `company.total_price` | `SUM(bento.price * order_items.quantity)` |
| 絞り込み | `q`（`GET /companies/rows`） | `WHERE ... ILIKE` |

アレルギーについては、注文登録画面の `<details>` で開く食品アレルギー表で利用しています。

| HTML | Python | PostgreSQL |
|---|---|---|
| 弁当 | `item.bento_name` | `bento.name` |
| アレルゲン | `item.allergens` | `allergens.name`（`bento_allergens` 経由） |

多対多の関係を、

```text
allergens
bento_allergens
```

という中間テーブルを含むスキーマで表現しています。

---

# 9. データベースアクセス

`app/db.py` がPostgreSQLへのアクセスを担当します。

主な関数：

| Function | 内容 |
|---|---|
| `get_connection()` | PostgreSQLへの接続を作成 |
| `fetch_companies()` | 会社一覧を取得 |
| `fetch_company_contacts(keyword)` | 会社の連絡先と注文実績を取得（`keyword` で絞り込み） |
| `fetch_bentos()` | 弁当一覧を取得 |
| `fetch_bento_allergens()` | 弁当ごとのアレルゲン一覧を取得 |
| `fetch_orders()` | 注文履歴を取得 |
| `fetch_order(order_id)` | 注文と明細を取得 |
| `insert_order(draft)` | 注文と明細を登録 |

ORMは使用せず、SQLを明示的に記述しています。

データベースから取得した行は、`Company`、`CompanyContact`、`Bento`、`OrderSummary`、`OrderItem` などのPydanticモデルへ変換します。

---

# 10. 起動

依存関係を同期：

```bash
uv sync
```

FastAPIを起動：

```bash
uv run uvicorn app.main:app --reload
```

ブラウザ：

```text
http://127.0.0.1:8000/
```

Swagger UI：

```text
http://127.0.0.1:8000/docs
```

なお、このアプリケーションの主要な画面はHTML/Jinja2による画面であり、Swagger UIはFastAPIが提供するAPIドキュメントです。

## 10.1 テストと静的解析

個別に実行する場合：

```bash
uv run ruff check .     # lint（select = ALL）
uv run ruff format .    # フォーマッタ
uv run mypy             # 型チェック（strict）
uv run pytest           # テスト
```

`mypy` に引数は渡しません。対象は `pyproject.toml` の `[tool.mypy] files` で `app` / `tests` と定義済みです。

テストは `db.get_connection` をフェイクの接続へ差し替えたうえで、FastAPIの `TestClient` から各ルートを呼び出します。SQLの結果行がPydanticモデルとテンプレートを通して正しく描画されるか、`parse_quantities` がフォームの値を正しく解釈するかを検証しており、**PostgreSQLが無くても実行できます**。

## 10.2 pre-commit フックとCI

チェック項目は `.pre-commit-config.yaml` に**一箇所だけ**定義し、ローカルのコミット時とCIの両方が同じ定義を実行します。

| | 実行方法 | 対象ファイル |
| --- | --- | --- |
| ローカル | `git commit` （フック経由） | ステージされたファイル |
| CI | `uv run pre-commit run --all-files` | リポジトリ全体 |

CIだけが厳しい／ローカルだけが厳しい、という状態が原理的に起こりません。チェックを追加・変更するときも `.pre-commit-config.yaml` だけを直せば両方に反映されます。

### 初回セットアップ

クローン後に一度だけ実行します。

```bash
uv sync
uv run pre-commit install
```

これで `git commit` のたびに次が走り、1つでも失敗するとコミットは中断されます。

| hook | 内容 |
| --- | --- |
| `uv-lock-check` | `pyproject.toml` と `uv.lock` の整合性（`uv lock --check`） |
| `ruff-check` | lint。自動修正可能なものは修正したうえで失敗させる |
| `ruff-format` | フォーマット。整形が入った場合は失敗させる |
| `mypy` | strict モードの型チェック |
| `pytest` | テスト |

`ruff-check` と `ruff-format` はファイルを書き換えてから失敗します。整形結果を確認して `git add` し直し、もう一度コミットしてください。

全ファイルに対して手動で走らせる場合（CIと同じ実行）：

```bash
uv run pre-commit run --all-files
```

緊急時にフックを飛ばす場合は `git commit --no-verify` を使えますが、CIでは同じチェックが走るため結局失敗します。

### CI

`.github/workflows/ci.yml` が `main` への push、全てのプルリクエスト、および手動実行（`workflow_dispatch`）で起動します。

1. `uv sync --locked --all-groups` — `uv.lock` を更新せずに同期する。ロックファイルがずれていればここで失敗する
2. `uv run pre-commit run --all-files --show-diff-on-failure` — フックと同一のチェックを実行する

`--show-diff-on-failure` を付けているため、フォーマット差分が原因で落ちた場合はCIのログに差分がそのまま出ます。

PostgreSQLはCIで起動しません。テストが `db.get_connection` を差し替えており、DBへ接続しないためです。

---

# 11. 現在のアプリケーション構成

現在の実装は、概ね次の構造になっています。

```mermaid
flowchart TD
    UI[Browser / Jinja2 HTML]
    API[FastAPI main.py]
    MODEL[Pydantic schemas.py]
    DBLAYER[PostgreSQL access db.py]
    DB[(PostgreSQL)]

    UI -->|GET /| API
    UI -->|GET /companies| API
    UI -->|POST /orders| API
    UI -->|GET /orders| API
    UI -->|GET /orders/complete| API
    UI -->|POST /orders/summary - HTMX| API
    UI -->|GET /companies/rows - HTMX| API

    API --> MODEL
    API --> DBLAYER
    DBLAYER --> DB
```

役割は次のように分かれています。

- `main.py`
  - HTTPリクエストを受け取る
  - フォームを解析する
  - Pydanticモデルを生成する
  - DB操作を呼び出す
  - Jinja2テンプレートを返す（ページ全体、またはHTMX向けの部分HTML）
- `schemas.py`
  - アプリケーションで扱うデータモデルを定義する
  - Pydanticによる値の制約を定義する
- `db.py`
  - PostgreSQLへの接続を行う
  - SQLを実行する
  - DBの行をPydanticモデルへ変換する

---

# 12. 設計上の方針

このデモでは、まず**理解しやすさを優先**します。

- ORMは使用しない
- SQLを明示的に記述する
- PostgreSQLの外部キーを利用する
- 多対多は中間テーブルで表現する
- 注文登録はトランザクションで処理する
- HTML/Jinja2を中心としたシンプルなフロントエンドにする
- 必要以上にフレームワークを導入しない
- CSSはクラスレスフレームワークに任せ、テンプレートに書かない
- 画面の更新はサーバーが返すHTMLで行い、手書きのJavaScriptは書かない
- Python側のデータモデルはイミュータブルに扱う

Pico.css と HTMX を入れても「必要以上にフレームワークを導入しない」という方針は
変わりません。どちらもビルド不要で、読み込みは `<link>` と `<script>` の各1行、
仮想DOMもコンポーネントモデルも持ち込まないためです。

むしろ、この2つは**テンプレートからノイズを取り除くために**入れています。

| | 導入前 | 導入後 |
|---|---|---|
| テンプレート合計 | 1,451行 | 310行 |
| テンプレート内のCSS | 944行 | 3行 |
| 手書きJavaScript | 134行 | 0行 |

削れた134行のJavaScriptは、主に金額の再計算でした。
現在その計算はPython側の `OrderItem` と `format_yen` だけが持っており、
注文概要パネルと注文完了画面が同じ結果を返すことが保証されます。
「同じ計算をJavaScriptとPythonに二重に書かない」ことが、
このリポジトリの本題（業務データをRDBとPythonでどう表現するか）と
合致していると考えています。

特に注文登録では、`OrderDraft` や `QuantitySelection` などのモデルを介して、フォームから受け取ったデータを明示的なデータ構造に変換してからDBへ渡します。

---

# 13. 現在実装されている機能

現在のPythonコードから確認できる範囲では、以下が実装済みです。

- 会社一覧の取得
- 弁当一覧の取得
- 弁当価格の表示
- メイン画面から開く食品アレルギー表（`<details>` アコーディオン）
- 会社・注文日・弁当数量を指定した注文登録
- 注文と注文明細のトランザクション処理
- 注文履歴の表示
- 注文ごとの合計金額の計算
- 個別注文の完了・詳細画面
- 存在しない注文への404応答
- 金額の「円」形式での表示
- 担当者・メールアドレス・電話番号を表示する取引先一覧画面
- 会社ごとの注文件数・最終注文日・累計金額の集計
- 取引先一覧のキーワード絞り込み（HTMX + SQLの `ILIKE` によるサーバー側処理）
- 入力に追従する注文概要パネル（HTMXによるサーバー側レンダリング）
- `base.html` の継承による共通レイアウト
- Pico.css によるレスポンシブ表示とダークモードの自動対応

---

# 14. 今後の拡張候補

現在すでに注文登録・注文履歴・注文詳細まで実装されているため、今後の拡張候補は次のようになります。

1. HTML/CSSの改善
2. 弁当・会社マスタのキャッシュ（注文概要パネルが毎回引き直しているため）
3. 入力値・存在する会社や弁当IDなどのバリデーション強化
4. テストの追加・拡充
5. Repository層などへの責務分離
6. Docker化
7. デプロイ環境への対応

特に `allergens` / `bento_allergens` は、注文画面の `<details>` で開く食品アレルギー表で利用しており、RDBの多対多関係を具体的に確認できます。

---

## 15. 最終的な目的

このデモの目的は、高機能なWebアプリケーションを作ることではありません。

**「業務上のデータをRDBでどのように表現し、それをFastAPIからどのように扱うか」**

を、小さく分かりやすい実例として説明できるようにすることを目的としています。

特に、

```mermaid
flowchart LR
    A[業務上の概念]
    B[RDBのテーブル]
    C[SQL]
    D[Pydanticモデル]
    E[FastAPI]
    F[HTML]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

という流れを一つのアプリケーションで確認できることを重視しています。
