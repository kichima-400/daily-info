# ホルムズ海峡 通過隻数データ取得ガイド

IMF PortWatch の無料 REST API を使って、ホルムズ海峡の日次通過隻数を取得する方法をまとめる。

---

## データソース概要

| 項目 | 内容 |
|---|---|
| 提供元 | IMF（国際通貨基金）/ Oxford Environmental Change Institute |
| データ種別 | 衛星 AIS（船舶自動識別システム）ベースの日次通過隻数 |
| 対象チョークポイント | ホルムズ海峡（`chokepoint6`） |
| 更新頻度 | **毎週火曜 JST 23:00**（米国東部時間 9:00）。最大7日程度のラグが生じる |
| 認証 | **不要**（API キーなし） |
| ライセンス | IMF オープンデータ（商用利用可） |
| 公式ページ | https://portwatch.imf.org/pages/chokepoint6 |

---

## API 仕様

### エンドポイント

```
GET https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query
```

### 主要クエリパラメータ

| パラメータ | 値 | 説明 |
|---|---|---|
| `where` | `portid='chokepoint6'` | ホルムズ海峡を指定 |
| `outFields` | `date,year,month,day,n_total` | 取得フィールド（後述） |
| `orderByFields` | `date DESC` | 最新日順に並べる |
| `resultRecordCount` | `7`（任意） | 取得件数。最大 1000 |
| `f` | `json` | レスポンス形式 |

### 主要レスポンスフィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `date` | number | Unix タイムスタンプ（ミリ秒） |
| `year` / `month` / `day` | number | 日付の各要素（日付文字列組み立てに使用） |
| `n_total` | number | その日の通過総隻数 |
| `n_tanker` | number | タンカーの隻数 |
| `n_container` | number | コンテナ船の隻数 |
| `n_dry_bulk` | number | バラ積み船の隻数 |
| `n_general_cargo` | number | 一般貨物船の隻数 |
| `n_roro` | number | ロールオン・ロールオフ船の隻数 |

### レスポンス例

```json
{
  "features": [
    {
      "attributes": {
        "date": 1775952000000,
        "year": 2026,
        "month": 4,
        "day": 12,
        "n_total": 8,
        "n_tanker": 3,
        "n_container": 2,
        "n_dry_bulk": 1,
        "n_general_cargo": 1,
        "n_roro": 1
      }
    }
  ]
}
```

---

## Python 実装例

```python
import requests

PORTWATCH_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
    "/Daily_Chokepoints_Data/FeatureServer/0/query"
)

def get_hormuz_transit(days: int = 7) -> list[tuple[str, int]]:
    """
    ホルムズ海峡の直近 N 日分の通過隻数を取得する。

    Args:
        days: 取得する日数（デフォルト 7）

    Returns:
        [(YYYY-MM-DD, n_total), ...] 日付昇順（古い→新しい）
    """
    params = {
        "where": "portid='chokepoint6'",
        "outFields": "date,year,month,day,n_total",
        "orderByFields": "date DESC",
        "resultRecordCount": days,
        "f": "json",
    }
    resp = requests.get(PORTWATCH_URL, params=params, timeout=20)
    resp.raise_for_status()

    features = resp.json().get("features", [])
    if not features:
        raise ValueError("データが取得できませんでした")

    rows = []
    for feat in reversed(features):  # 古い順に並べ替え
        a = feat["attributes"]
        date_str = f"{a['year']}-{a['month']:02d}-{a['day']:02d}"
        rows.append((date_str, int(a["n_total"])))
    return rows


if __name__ == "__main__":
    for date, count in get_hormuz_transit():
        print(f"{date}: {count} 隻")
```

### 実行結果例

```
2026-04-06: 5 隻
2026-04-07: 4 隻
2026-04-08: 4 隻
2026-04-09: 9 隻
2026-04-10: 5 隻
2026-04-11: 11 隻
2026-04-12: 8 隻
```

### 依存ライブラリ

```
requests>=2.28.0
```

---

## 注意事項

- **データラグ**: 週次更新のため、最新データは最大7日程度前になる。
- **AIS の限界**: GPS ジャミング・AIS スプーフィング・信号消失（going dark）の影響を受けることがある。実際の通過数と差異が生じる可能性がある。
- **ページネーション**: 1 リクエストあたり最大 1000 件。大量取得時は `resultOffset` で offset 指定が必要。
- **他チョークポイント**: `portid` を変更することでスエズ運河（`chokepoint1`）等の他の海峡にも対応できる。詳細は https://portwatch.imf.org/ を参照。
