# 古籍残页转写拼接 API

提交两段含 `?`（未辨认字）的转写文本，服务仅将**左段后缀**与**右段前缀**对齐，
按给定规则打分，返回最高分对齐的原文区间、逐列对齐结果与拼接文本。基于 Python + FastAPI 实现。

## 单条命令启动

依赖已在镜像内安装，无需本机准备 Python 环境：

```bash
docker compose up --build -d
```

启动后：

| 项目 | 地址 |
| --- | --- |
| 对齐接口 | <http://localhost:8000/align> （`POST`） |
| 健康检查 | <http://localhost:8000/health> |
| 根路径 | <http://localhost:8000/> |
| Swagger 文档 | <http://localhost:8000/docs> |
| ReDoc 文档 | <http://localhost:8000/redoc> |

监听端口为 **8000**（宿主机同样映射到 `8000`，可在 `docker-compose.yml` 中修改）。

停止服务：

```bash
docker compose down
```

## 接口说明

### POST /align

请求体（JSON）：

```json
{
  "left": "天?下",
  "right": "天下太平"
}
```

| 字段 | 说明 |
| --- | --- |
| `left` | 左段转写文本，`?` 表示未辨认字；仅其后缀参与对齐，前缀不计分 |
| `right` | 右段转写文本，`?` 表示未辨认字；仅其前缀参与对齐，后缀不计分 |
| `require_question` | 可选，默认 `true`：要求两段文本均至少含一个 `?`，否则返回 400；置 `false` 可对齐不含 `?` 的文本 |
| `max_len` | 可选，单段最大字符数（默认 1000） |

调用示例：

```bash
curl -X POST http://localhost:8000/align \
  -H "Content-Type: application/json" \
  -d '{"left":"天?下","right":"天下太?平"}'
```

响应示例：

```json
{
  "score": 2,
  "aligned_pairs": 2,
  "score_breakdown": {
    "match": 1,
    "mismatch": 0,
    "unknown": 1,
    "gap_open": 0,
    "gap_extend": 0
  },
  "left_range": { "start": 2, "end": 3, "text": "?下" },
  "right_range": { "start": 1, "end": 2, "text": "天下" },
  "columns": [
    {
      "index": 1,
      "type": "unknown",
      "score": 0,
      "left_pos": 2,
      "left_char": "?",
      "right_pos": 1,
      "right_char": "天",
      "merged_char": "天"
    },
    {
      "index": 2,
      "type": "match",
      "score": 2,
      "left_pos": 3,
      "left_char": "下",
      "right_pos": 2,
      "right_char": "下",
      "merged_char": "下"
    }
  ],
  "merged_text": "天下",
  "conflicts": [],
  "substitutions": [
    {
      "column": 1,
      "unknown_side": "left",
      "unknown_pos": 2,
      "known_side": "right",
      "known_pos": 1,
      "known_char": "天"
    }
  ],
  "unresolved_questions": []
}
```

响应字段说明：

| 字段 | 说明 |
| --- | --- |
| `score` | 最优对齐总分（逐列得分之和） |
| `aligned_pairs` | 字符对字符的对齐列数（至少为 1） |
| `score_breakdown` | 相同字、异字、`?` 配对、空缺首字/延续字的计数 |
| `left_range` / `right_range` | 参与对齐的原文区间；位置为 **1 起始、闭区间**，并附原文片段。左段区间必为后缀，右段区间必为前缀 |
| `columns` | 逐列对齐：列号、类型、本列得分、双方原文位置与字形、拼接入列字 |
| `merged_text` | 拼接文本，顺序与 `columns` 一致 |
| `conflicts` | 异字冲突清单：列出双方原文位置（`left_pos`/`right_pos`）及双方字形（`left_char`/`right_char`） |
| `substitutions` | 以已知字替换 `?` 的清单：未辨认字所在方/位置、已知字所在方/位置与字形 |
| `unresolved_questions` | 双方皆为 `?`、无法补字的列 |

列类型：`match`（相同字）、`mismatch`（异字）、`unknown`（含 `?`）、
`gap_left`（左字对空缺）、`gap_right`（空缺对右字）。

## 计分与裁决规则

仅左段后缀 `left[i:]` 与右段前缀 `right[:j]` 参与对齐；左段未参与的前缀与
右段未参与的后缀不计分。对齐结果至少包含一对字符对字符的列。

逐列得分：

- 相同已知字：**+2**
- 任一方为 `?`：**0**（双方皆为 `?` 亦为 0，拼接处保留 `?`）
- 异字：**-2**
- 空缺列：同一方向连续空缺**首字 -3，其后每字 -1**（仿射空缺罚分）

最优选择顺序：

1. 总分最高；
2. 总分相同，字符对字符的对齐列数最多；
3. 仍相同，左段起点 `i` 最小。

拼接规则：

- 已知字与 `?` 配对：以已知字替换 `?`（记录于 `substitutions`）；
- 两个已知异字：保留**左段字形**，并在 `conflicts` 中列出双方原文位置及字形；
- 空缺列：取未空缺一方的字；
- 双方皆为 `?`：保留 `?` 并记入 `unresolved_questions`。

## 算法

带仿射空缺罚分的半全局（suffix-prefix / overlap）动态规划，三状态
`M`（字-字）、`V`（左字-空缺）、`H`（空缺-右字）加自由起点，时间与空间
复杂度均为 O(m·n)。单段长度默认上限 1000 字。

## 本地开发与测试（可选）

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest
```

## 项目结构

```
app/
  aligner.py    # 对齐算法与计分、拼接
  main.py       # FastAPI 路由与请求校验
tests/          # 算法与接口测试
Dockerfile
docker-compose.yml
requirements.txt
```
