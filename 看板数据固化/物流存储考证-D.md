# 物流存储考证-D（P37 SCFI 运价指数 + P58 存储芯片价格）

考证日期：2026-10-27。考证人：数据采集（D）。
原则：全部数值取自公开报道原文或数据源官方页面当日快照，禁止推算编造；推算值（仅1处，见B-4）已注明推算链并有两源交叉。

---

## A. 存储芯片价格（P58，五品类，2026-10-27 采集）

主数据源：TrendForce 官网现货价页（可直接抓取的固定页，含下述全部条目，取当日 Session Average）：
- DRAM：https://www.trendforce.com/price/dram/dram_spot
- NAND Flash：https://www.trendforce.com/price/flash/flash_spot

| 数值(USD) | 品类（现货页条目原名） | 来源 | 日期 | URL |
|---|---|---|---|---|
| 47.043 | DDR4 8Gb (1Gx8) 3200，Session Average | TrendForce 现货价页（直接抓取） | 2026-10-27 | https://www.trendforce.com/price/dram/dram_spot |
| 82.623 | DDR4 16Gb (2Gx8) 3200，Session Average | TrendForce 现货价页（直接抓取） | 2026-10-27 | 同上 |
| 61.333 | DDR5 16Gb (2Gx8) 4800/5600，Session Average | TrendForce 现货价页（直接抓取） | 2026-10-27 | 同上 |
| 18.365 | NAND 256Gb TLC，Session Average | TrendForce 现货价页（直接抓取） | 2026-10-27 | https://www.trendforce.com/price/flash/flash_spot |
| 18.592 | NAND 512Gb TLC，Session Average | TrendForce 现货价页（直接抓取） | 2026-10-27 | 同上 |

媒体交叉佐证（转引 TrendForce 数据的公开报道）：

| 佐证内容 | 品类 | 来源媒体 | 报道日期 | URL |
|---|---|---|---|---|
| DDR5 16Gb 4800/5600 现货均价较上日 +0.28%；DDR4 16Gb(2Gx8)3200、DDR4 8Gb(1Gx8)3200 持平 | DDR4/DDR5 | 观点网 | 2026-10-16 | https://www.guandian.cn/m/show/614201 |
| DDR5 16Gb 现货均价约 $60.60、周涨0.28%；10-23 日涨0.16% | DDR5 | 富途资讯（转引TrendForce，经检索摘要） | 2026-10-16 / 2026-10-23 | （检索摘要，未存档原文URL） |
| DDR5 16Gb (2Gx8) 4800/5600 当日 Session Average $57.933（日内区间 $43.50–69.50） | DDR5 | Semiconductor Insider（X帖，转引TrendForce） | 2026-10-01 | https://x.com/SemiconductorsX/status/2105636978880631283 |
| 16GB DDR4-3200 现货均价 $78.75，反超同规格 DDR5（$36.6） | DDR4 | 财经网 | 2026-02 | https://www.mycaijing.com/article/detail/563522?source_id=40 |
| DDR4 8Gb 现货自2025年低点约$3.2涨至$15–17；2026Q1 DRAM合约价环比+90%~95% | DDR4 | 钛媒体 | 2026（年初） | https://www.tmtpost.com/7911771.html |
| 512Gb TLC Flash Wafer 报价约 $22.00（口径为wafer报价中心，与TrendForce颗粒现货口径不同，仅作高位佐证） | NAND | memorys.com 报价中心 | 2026-10-14 | （检索摘要，未存档原文URL） |
| 512Gb TLC 因旧制程转产供应急缩，11月合约价月增超65%；256Gb TLC 供给缩减 | NAND | 经济日报(台湾)转引TrendForce | 2025-12-01 | https://money.udn.com/money/story/5612/9174566 |

历史已留存行（本日之前采集器抓取值，保留在CSV）：
- 2026-10-23：DDR5 16Gb = 61.267，NAND 512Gb TLC = 18.833（TrendForce现货价页当日Session Average，采集器首次运行留存）。

### 固定页可得性结论（P58）
- **可得**：TrendForce 英文现货价页 /price/dram/dram_spot 与 /price/flash/flash_spot 即固定公开页，两页合计覆盖全部5个品类，且结构稳定（2026-10-23 与 10-27 两次抓取解析一致）。已将采集器 collect_P58_dram_nand.py 从2品类扩为5品类，维持页面解析方案。
- **无 RSS**：trendforce.com/rss、/rss.xml、/presscenter/news/rss 等均404（2026-10-27 探测）。
- 备用人工源：观点网每日发布"TrendForce现货均价"摘要稿（含DDR4/DDR5各条目涨跌），适合RPA手册收录作人工备份；CFM闪存市场 chinaflashmarket.com/price 为另一免费报价看板（口径不同）。

---

## B. SCFI 上海出口集装箱运价指数（P37）历史回填考证（10周）

官方接口结论：上海航交所官网 sse.net.cn 的"多期查询"接口 `/index/mutipleIndex`（AJAX，返回JSON）**需登录**，"单期查询"表单POST同样不返回历史数据（2026-10-27 实测）。故历史逐周值按公开报道手工考证，采集器 collect_P37_SCFI.py 保持现状（每周抓当期上期两期，官网免登录）。

发布节奏考证：正常每周五发布；2026-09-25 为中秋假期，该期提前至 9-24（周四）发布；国庆长假前的 10-02 期提前至 9-30（周三）发布（东方财富快讯"截至9月30日"为原文依据），10-09（周五）恢复。

| 数据日期 | 综合指数 | 来源媒体 | 报道日期 | URL / 依据 |
|---|---|---|---|---|
| 2026-08-07 | 3276.14 | 证券时报e公司（腾讯新闻转载）；搜狐财经同值 | 2026-08-08 | https://news.qq.com/rain/a/20260808A046BF00 ；https://www.sohu.com/a/1060268600_121157270 |
| 2026-08-14 | 3355.24 | Container News「SCFI 2026周度图表」W33 | 2026-10-27访问 | https://container-news.com/scfi/ （另与8-21报道环比+54.39点反推相符） |
| 2026-08-21 | 3409.63 | NoteMatch运价看板（hscodes.net，转引上海航交所，带日期序列） | 2026-10-27访问 | https://hscodes.net/topics/freight-market |
| 2026-08-28 | 3509.53 | 财联社9-4报道"环比+80.52点"反推（3590.05−80.52）；Container News图表、hscodes均同值 | 2026-09-04 | https://m.cls.cn/detail/2474228 。注：经济观察网当日稿写3509.54（http://www.eeo.com.cn/2026/0828/1014660.shtml ），与财联社涨跌数不自洽，判为笔误 |
| 2026-09-04 | 3590.05 | 财联社快讯（"截至9月4日…报3590.05点，与上期相比上涨80.52点"） | 2026-09-04 | https://m.cls.cn/detail/2474228 |
| 2026-09-11 | 3662.18 | 雪球（"9月11日报3662.18点，累计七连涨"）；浦银资讯同值 | 2026-09-24 | https://www.xueqiu.com/3124808626/410433247 |
| 2026-09-18 | 3687.83 | 浦银资讯（"截至9月18日SCFI报3687.83"）；Container News图表同值 | 约2026-09-19 | https://webnewslt1.pobo.net.cn/Data/NENG/6776335.HTML （现404，标题存于检索快照） |
| 2026-09-24 | 3686.62 | 东方财富9-30快讯之上期值（"与上期相比下跌24.32点"：3686.62−24.32=3662.30）；中秋9-25提前发布 | 2026-09-30 | https://finance.eastmoney.com/a/202609303887674239.html |
| 2026-09-30 | 3662.30 | 东方财富快讯（"截至9月30日…SCFI报3662.30点，与上期相比下跌24.32点"） | 2026-09-30 | https://finance.eastmoney.com/a/202609303887674239.html |
| 2026-10-09 | 3664.11 | NoteMatch运价看板（带日期序列）；Macromicro同值 | 2026-10-27访问 | https://hscodes.net/topics/freight-market |
| 2026-10-16 | 3679.58 | 上海航交所官网当期"上期"值（原有，官网免登录页） | 2026-10-23采集 | https://www.sse.net.cn/index/singleIndex?indexType=scfi |
| 2026-10-23 | 3681.34 | 上海航交所官网当期值（原有，官网免登录页） | 2026-10-27采集复核 | 同上 |

图表总源交叉验证：Container News「SCFI」专栏内嵌 2026 年逐周图表数据（Week3–Week43，41点），与上述已核值的12个散点全部吻合（其中8-28差0.01，按财联社涨跌数裁定3509.53）：
https://container-news.com/scfi/

其他顺带考证锚点（未入CSV，仅佐证图表可信度）：7-11=3184.83（搜狐 https://www.sohu.com/a/1048805129_121124376 ，2026-07-11）；7-17=3080.31（经济观察网 http://www.eeo.com.cn/2026/0717/962409.shtml ，2026-07-17）；7-24=3062.95（Yahoo股市/检索摘要）；7-31=3205.97（搜狐 https://www.sohu.com/a/1060918152_120987862 ，2026-08-10，含美西6229美元/FEU、美东9054美元/FEU、欧线3039美元/TEU）；5-15=2140.66、5-22=2218.15、3-20=1706.95（Yahoo台湾/检索摘要）。

### 固定页可得性结论（P37）
- **官方历史接口不可用**（需登录）；官网当期页免登录可抓（采集器现状，每周五后运行）。
- **可得固定页**（免登录、可定期抓取的辅助源）：
  - Container News SCFI专栏 https://container-news.com/scfi/ ——页面内嵌 `DAEXTDAUC_DATA` JSON，含2026全年逐周SCFI（更新至最新一周），可脚本化解析（本周已验证解析方法）；
  - NoteMatch运价看板 https://hscodes.net/topics/freight-market ——内嵌 `scfiData` JSON（近90天带日期散点，约6-8个点，较稀疏）；
  - 财联社/东方财富每周快讯（"SCFI综合指数报XXXX.XX点"）格式统一，适合RPA关键词监控。
- 如需免登录官方历史，可在航交所免费注册后人工导出（RPA手册可收录此操作）。

---

## C. 变更清单
- `CSV数据/大宗商品-P37-SCFI运价指数.csv`：新增2026-08-07~2026-10-09共10行（历史为手工考证）；2026-10-16/10-23两行保持原状。
- `CSV数据/产品品类-P58-存储芯片价格.csv`：表头扩为5品类（DDR4_8Gb/DDR4_16Gb/DDR5_16Gb/NAND_256Gb/NAND_512Gb），10-23旧行值已迁移保留。
- `采集脚本/collect_P58_dram_nand.py`：扩为5品类解析（DRAM页3条+NAND页2条），量级校验按品类分设。
- `采集脚本/collect_P37_SCFI.py`：未改动。
