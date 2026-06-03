# 药点 MediPoint — 后端 API (Backend)

> **服务名:** MediPoint API
> **版本:** 1.0
> **职责:** 为 [MediPoint 前端](../MediPoint) 提供真实数据 (ERP 库存 / 政府公告 / 微博小红书 / AI 决策建议 / 药师 RAG 助手)
> **数据:** 福建省 3 家零售药店的示例库存 + 真实公开政府公告 + DeepSeek LLM

---

## 📖 项目简介

**药点 MediPoint** 是一个面向药店的智能商情系统。后端基于 FastAPI 实现，核心能力：

1. **真实数据聚合** — 从 MongoDB 拉取 `db.inventory` + `db.alerts` + `db.raw_articles` + `db.daily_category_summary` 等
2. **6 源政府公告抓取** — 福建卫健委 (疫情公告 + 通知公告) / 福建 CDC / NMPA / 中国 CDC (月报 + 流感周报)，并行执行，自动降级
3. **AI 决策建议** — 库存 × 舆情交叉分析，生成「补货 / 促销」建议块，每个 block 自动关联相关政府公告 URL，按信心等级 (A/B/C) 排序
4. **AI 行销话术** — 异步生成 (12h 内容哈希缓存)，药师行销话术与采购补货理由分别生成
5. **RAG 药师 AI 助手** — TF-IDF + Jieba 检索药品说明书 / SOP / FAQ / 公告，DeepSeek 流式回答，相关性弱时自动降级为通用 LLM
6. **SSE 流式聊天** — `/api/chat` 走 Server-Sent Events，前端逐字渲染

---

## 🛠 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.110+ |
| ASGI 服务器 | Uvicorn (含 reload 模式) |
| 数据库 | MongoDB 4.4+ (pymongo 驱动) |
| LLM 客户端 | DeepSeek (`api.deepseek.com`, OpenAI 兼容协议) |
| RAG 检索 | scikit-learn TF-IDF + jieba 中文分词 (进程内 in-memory 索引) |
| HTML 解析 | BeautifulSoup4 + lxml |
| 反爬绕过 | cloudscraper (FJ CDC / NMPA) |
| 时区 | zoneinfo (Asia/Shanghai) |
| Python | 3.11+ |

---

## 📁 目录结构

```
MediPoint_backend/
├── app.py                          # FastAPI 入口 + lifespan 启动后台任务
├── requirements.txt                # Python 依赖
├── .env                            # 环境变量 (本地)
├── README_HF.md                    # Hugging Face Spaces 部署元数据
├── api/                            # (预留) 公共 API 类型
├── db/
│   └── mongo.py                    # pymongo 客户端
├── routers/
│   ├── chat.py                     # /api/chat (SSE 流式 RAG 聊天)
│   ├── crawler.py                  # /api/crawler/run (手动触发抓取)
│   ├── dashboard.py                # /api/dashboard/weekly-report
│   ├── decisions.py                # /api/decisions (补货/促销建议)
│   ├── decisions_scripts.py        # /api/decisions/script (异步脚本)
│   ├── mock.py                     # /api/mock/* (ENABLE_MOCK 开关)
│   ├── rag_router.py               # /api/rag/* (RAG 索引管理)
│   ├── regulations.py              # /api/regulations (法规查询)
│   └── sentiment.py                # /api/sentiment (舆情)
├── services/
│   ├── crawlers.py                 # 6 源并行入口
│   ├── crawlers_fjwjw.py           # 福建卫健委 (yqgg + tzgg)
│   ├── crawlers_fjcdc.py           # 福建 CDC (走 static_cache 兜底)
│   ├── crawlers_nmpa.py            # NMPA (走 static_cache 兜底)
│   ├── crawlers_cdc_cn.py          # 中国 CDC (月报 + 流感周报)
│   ├── static_cache_fjcdc.py       # FJ CDC 静态兜底数据
│   ├── static_cache_nmpa.py        # NMPA 静态兜底数据
│   ├── decision_scripts.py         # LLM 脚本缓存 (内容哈希失效)
│   ├── entity_keywords.py          # 实体词典 (药品/疾病/症状/品牌)
│   ├── sku_category_map.py         # SKU → 标准化 category 映射
│   ├── trend_analyzer.py           # 关键词热度 + 7 日时序
│   ├── sentiment_classifier.py     # 调用入口
│   ├── dashboard.py                # 周报聚合
│   ├── decisions.py                # 决策引擎
│   ├── rag.py / rag_retriever.py   # RAG 索引 + 检索
│   ├── rag_prompt.py               # RAG prompt 模板
│   ├── data_drug_monographs.py     # 53 条药品说明书静态数据
│   ├── data_sops.py                # 门店 SOP 静态数据
│   ├── seed_kb.py                  # 灌入 KB 静态数据
│   └── crawler_status.py           # 抓取状态查询
├── util/
│   ├── llm.py                      # DeepSeek 客户端 + 营销对生成 + 情感分类
│   ├── sentiment_classifier.py     # LLM 分类 + Mongo 缓存
│   ├── config.py                   # Env 类 (从 .env 读取)
│   └── auth.py                     # HTTPBasic 鉴权
├── scripts/
│   ├── seed_inventory.py           # 给 3 家店灌示例库存
│   └── cleanup_fjwjw.py            # 清理 FJ WJW 重复 alert
├── __pycache__/                    # 缓存
└── .github/                        # CI
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd MediPoint_backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 启动 MongoDB

```bash
# 本地 MongoDB (无认证)
mongod --dbpath /path/to/data --port 27017
# 或 Docker
docker run -d -p 27017:27017 --name medipoint-mongo mongo:6
```

### 3. 配置环境变量

复制 `.env.example` (如有) 或直接编辑 `.env`：

```bash
MongoDB_URL=mongodb://localhost:27017
DEEPSEEK_API_KEY=sk-...                # 必填, 从 https://platform.deepseek.com 获取
DOCS_USERNAME=admin                   # Swagger / OpenAPI 鉴权
DOCS_PASSWORD=admin123
PORT=3000
RELOAD=true                           # 开发 true / 生产 false
ENABLE_MOCK=true                      # 启用 /api/mock/* 路由
RUN_CRAWLER_ON_STARTUP=true           # 启动时后台执行 6 源抓取
STARTUP_CRAWL_MIN_INTERVAL_HOURS=6    # 6 小时内不重复抓取
```

### 4. (可选) 灌入示例库存

```bash
python scripts/seed_inventory.py
# 输出: seeded 31 inventory records for date 2026-06-03 (S001=11, S002=10, S003=10)
```

### 5. 启动后端

```bash
python app.py
# 或
uvicorn app:app --host 0.0.0.0 --port 3000 --reload
```

启动后会自动：
- 灌静态 KB 到 Mongo
- 重建 RAG 索引 (in-memory)
- 启动后台抓虫 (6 源并行)
- 启动后台 sentiment 分类 (最近 60 天未分类 alert)

### 6. 验证

```bash
curl http://localhost:3000/health
# {
#   "status": "ok",
#   "mongo": "ok",
#   "llm_configured": true,
#   "crawler_last_run": "2026-06-03T...",
#   ...
# }

curl -u admin:admin123 http://localhost:3000/api/decisions?store=S001 | head
```

---

## 🌐 核心 API 速查

| Method | Path | 说明 | 鉴权 |
|--------|------|------|------|
| GET | `/health` | 健康检查 (mongo + llm + crawler) | ✗ |
| GET | `/api/dashboard/weekly-report?store=S001` | 周报数据 (KPI + 建议 + 舆情) | ✓ |
| GET | `/api/decisions?store=S001` | 补货 / 促销建议 (同步, 不含 LLM) | ✓ |
| GET | `/api/decisions/script?key=S001\|2026-06-03\|Restock\|感冒/退烧` | 单条 LLM 脚本 (含缓存) | ✓ |
| GET | `/api/sentiment?source=GovNotice&limit=50` | 舆情列表 + 关键词热度 + 7 日时序 | ✓ |
| GET | `/api/regulations?source=all&limit=200` | 法规 / 公告查询 | ✓ |
| POST | `/api/chat` | SSE 流式 RAG 聊天 (DeepSeek) | ✓ |
| POST | `/api/crawler/run` | 手动触发 6 源抓取 | ✓ |
| GET | `/docs` | Swagger UI (HTTPBasic) | ✓ |

> **鉴权:** 全部 `/api/*` 走 HTTP Basic，账号 = `.env` 中 `DOCS_USERNAME` / `DOCS_PASSWORD`

---

## 🗄 MongoDB 数据模型

| Collection | 来源 | 关键字段 |
|------------|------|---------|
| `db.alerts` | 6 源爬虫 | `url` (unique), `title`, `summary`, `source` (FJ_WJW/FJ_CDC/NMPA/CN_CDC), `agency`, `category`, `risk_level`, `published_at`, `crawled_at`, `crawled_via` (live/static_fallback) |
| `db.raw_articles` | PTT/Dcard/GoogleNews (历史 demo) | `source`, `title`, `content`, `url`, `crawled_at`, `intent`, `tags` |
| `db.inventory` | ERP 同步 (或 seed) | `store_id`, `sku_id`, `sku_name`, `category`, `closing_on_hand`, `margin`, `sales_7d`, `date` |
| `db.daily_category_summary` | ERP 同步 | `date`, `store_id`, `category`, `revenue`, `gross_profit` |
| `db.drug_monographs` | seed_kb 静态 | `drug_name`, `category`, `indications`, `dosage`, `side_effects`, `contraindications`, `source` |
| `db.sop_entries` | seed_kb 静态 | `title`, `scenario`, `steps` |
| `db.decision_scripts` | 运行时 LLM 缓存 | `_key` (store\|date\|action\|category\|content_hash), `talking_points`, `upsell`, `reason`, `generated_at` |
| `db.crawler_status` | 单条 | `last_run`, `results` (各 source 上次抓取统计) |

**索引:**
- `alerts`: `url` (unique), `(source, published_at)`, `crawled_at`
- `inventory`: `(store_id, date, closing_on_hand)`
- `daily_category_summary`: `(date, store_id)`

---

## 🔄 启动流程 (Lifespan)

`app.py:80` 的 `@asynccontextmanager` 启动时按以下顺序后台运行：

```
1. _index_worker   →  seed_kb.seed_if_empty() + rag_service.reindex_all()
2. _crawl_worker   →  run_all_crawlers()  (6 源并行, ThreadPoolExecutor)
3. _sentiment_worker → classify_pending_alerts(batch=30, since_days=60)
```

每个 worker 用独立 `threading.Event` 标记完成，shutdown 时按 worker 分别 `wait(timeout=N)`，避免互相短电路。

---

## 🧠 AI 决策引擎 (`services/decisions.py`)

1. 取该门店当日 `db.inventory` 中低库存 (`<30`) / 高库存 (`>100`) 的 SKU
2. 按 SKU 名称前缀归一化到 `STANDARD_CATEGORIES` (19 个标准品类)
3. 每个 category 一个 block, 关联 14 天窗内的相关政府公告 (优先 `affected_categories` 字段, fallback 到 title 关键词)
4. 信心等级: `High risk alert + 库存<15 → A`, `Medium + 库存<30 → B`, 否则 `C`
5. 主接口同步返回, **LLM 字段留空 + 给 `script_key`**
6. 前端按 `script_key` 调 `/api/decisions/script` 异步拉取 `talking_points` / `upsell` / `reason`

**LLM 脚本缓存** (`services/decision_scripts.py`):
- 公开 key: `store_id|date|action|category`
- 实际 key: `公开 key + content_hash(sku_id+stock+margin)`
- 库存一变化, content_hash 变化, 缓存自动失效
- 12h TTL (兜底, 通常用不上)
- `upsell` 用静态表查品类关联产品 (同方向, 不跳品类)

---

## 🛡 安全 / 限流

- 全 `/api/*` 走 HTTP Basic, `.env` 中 `DOCS_USERNAME` / `DOCS_PASSWORD`
- CORS allowlist: `http://localhost:5173`, `http://localhost:5174`, `https://uie47061.github.io` + `FRONTEND_ORIGIN` 环境变量
- LLM 限流: DeepSeek 60 RPM, sentiment 分类 1.1s 间隔串行调用
- 抓虫失败/超时自动降级到 `static_cache_*` 兜底 (FJ CDC / NMPA)
- MongoDB 唯一索引 `alerts.url` 防止重复
- Prompt injection 防御: RAG 检索内容用 `===UNTRUSTED_DATA_BEGIN/END===` 包裹, system 明确告知 LLM 视为数据不执行

---

## 🧪 常用排错

**1. `llm_configured: false`**
检查 `.env` 中 `DEEPSEEK_API_KEY` 是否设置。

**2. `mongo: error`**
确认 `mongod` 在跑 (`mongodb://localhost:27017` 可连)。

**3. `decisions` 返回 `restock: []`**
`db.inventory` 为空 — 跑 `python scripts/seed_inventory.py`。

**4. `sentiment?source=Weibo` 返回 0 条**
`db.raw_articles` 中无 Weibo 数据 — 当前只有 PTT/Dcard/GoogleNews 真实数据, Weibo/小红书是 mock。

**5. RAG 助手回答很慢**
首次调用会重建 RAG 索引 (约 1s, in-memory 一次性), 之后命中缓存。DeepSeek 自身流式输出约 3-8s。

**6. 启动时报 `ModuleNotFoundError: No module named 'db'`**
当前目录必须在 `MediPoint_backend/` 内, 或 `PYTHONPATH` 包含该路径。

---

## 📜 许可

MIT
