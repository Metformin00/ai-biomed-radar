# AI × BioMed Paper Radar

一个静态优先的学术 RSS 追踪网站，用于监控 **人工智能 × 生物医药 / 流行病学 / 生物信息学** 相关期刊、预印本和主题检索源。

## 功能

- 论文卡片流
- 关键词检索
- 期刊 / 来源筛选
- 主题标签筛选
- 近 7 / 30 / 90 天筛选
- 热门标签和趋势条形图
- 本地收藏
- RSS/Atom 自动抓取
- GitHub Actions 定时更新
- GitHub Pages 静态部署

## 本地运行

```bash
cd ai_biomed_radar
python -m http.server 8000
```

浏览器打开：

```text
http://localhost:8000
```

## 更新数据

```bash
pip install -r requirements.txt
python scripts/update_feeds.py
```

更新后会生成：

```text
data/articles.json
data/trends.json
```

## 添加 RSS 源

编辑：

```text
config/feeds.json
```

示例：

```json
{
  "name": "Nature Medicine",
  "journal": "Nature Medicine",
  "url": "https://www.nature.com/nm.rss",
  "group": "clinical_ai",
  "is_preprint": false
}
```

## 添加标签

编辑：

```text
config/tags.json
```

第一版采用关键词规则自动打标签。你可以继续增加关键词，或在 `scripts/update_feeds.py` 中接入 LLM 分类。

## GitHub Pages 部署

1. 新建 GitHub 仓库。
2. 上传本项目所有文件。
3. Settings → Pages。
4. Source 选择 `Deploy from a branch`。
5. Branch 选择 `main`，目录选择 `/root`。
6. 访问生成的 Pages 地址。

## 自动更新

项目已包含：

```text
.github/workflows/update.yml
```

默认每天 UTC 03:10 运行一次 RSS 抓取并提交更新后的 `data/articles.json`。

## 翻译功能

默认关闭翻译，避免依赖外部 API。

如需开启：

1. 在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
2. 修改 `.github/workflows/update.yml`：
   - `ENABLE_TRANSLATION: "true"`

## 重要说明

- `data/articles.json` 初始包含示例数据，不是真实论文库。
- 部分 RSS URL 可能因期刊平台调整而变化，上线前建议逐个验证。
- Lancet、PubMed、Oxford Academic 的主题 RSS 通常建议从官网搜索页面生成后复制到 `config/feeds.json`。
