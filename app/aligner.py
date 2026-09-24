"""古籍残页转写拼接 —— 对齐核心算法。

规则
----
仅将左段后缀 L[i:] 与右段前缀 R[:j] 对齐（左段前缀 L[:i]、右段后缀
R[j:] 不参与、不计分）。对齐至少须包含一对字符列（非空缺列）。

逐列计分：

* 相同已知字：+2
* 任一方为 "?"（未辨认字）：0
* 异字：-2
* 空缺列采用仿射罚分：连续空缺首字 -3，其后每字 -1

同分裁决：对齐字符对数最多 → 左段起点 i 最小。

算法：带仿射空缺罚分的半全局（suffix-prefix / overlap）动态规划，
状态 M（字-字）/ V（左字-空缺）/ H（空缺-右字）/ S（自由起点）。
为在 O(mn) 内同时完成两级同分裁决，把 (分数, 字符对数, -左起点)
按字典序编码进一个整数，直接比较大小即可。
"""

from __future__ import annotations

MATCH_SCORE = 2
MISMATCH_SCORE = -2
UNKNOWN_SCORE = 0
GAP_OPEN = -3
GAP_EXTEND = -1
UNKNOWN = "?"

# DP 状态编号（回溯指针前驱用）
ST_M = 0  # 末列为 左字-右字
ST_V = 1  # 末列为 左字-空缺
ST_H = 2  # 末列为 空缺-右字
ST_S = 3  # 自由起点：尚未消耗任何列


def _pair_score(x: str, y: str) -> int:
    """字符对列得分：? 与任意字（含 ?）配对均为 0。"""
    if x == UNKNOWN or y == UNKNOWN:
        return UNKNOWN_SCORE
    return MATCH_SCORE if x == y else MISMATCH_SCORE


class AlignmentError(ValueError):
    """输入不合法或无法产生有效对齐。"""


def align(left: str, right: str, max_len: int = 1000) -> dict:
    """计算最高分后缀-前缀对齐并返回结构化结果。

    返回值各位置均为 1 起始、区间为闭区间。
    """
    if not isinstance(left, str) or not isinstance(right, str):
        raise AlignmentError("left 与 right 必须为字符串")
    left = left.strip()
    right = right.strip()
    if not left or not right:
        raise AlignmentError("left 与 right 均须为非空文本")
    if len(left) > max_len or len(right) > max_len:
        raise AlignmentError(f"单段长度不得超过 {max_len} 个字符")

    m, n = len(left), len(right)
    L, R = left, right

    # ---- 字典序整数编码 ----
    # 编码值 = score*POFF + pairs*IOFF - start_i + BIAS
    # 位域：start_i ∈ [1,L0]；pairs ∈ [0,L0]。
    # IOFF 大于 start_i 项跨度；POFF 大于 pairs 项跨度，
    # 故编码值的大小顺序恰为 (分数, 对数, -起点) 的字典序。
    L0 = max_len
    IOFF = L0 + 1
    POFF = (L0 + 1) * IOFF
    # 最低可能编码值（最小分数、0 对、起点 L0）仍须为正数
    BIAS = -(GAP_OPEN * L0 * POFF - L0) - 1
    NEG = -1  # 所有合法编码值均为正数

    def enc(score: int, pairs: int, start_i: int) -> int:
        return score * POFF + pairs * IOFF - start_i + BIAS

    # 每个状态一张 (m+1)×(n+1) 表；回溯表只需要 M/V/H 三态，
    # 值为前驱状态编号，遇 ST_S 即到达自由起点。
    def table():
        return [[NEG] * (n + 1) for _ in range(m + 1)]

    M, V, H, S = table(), table(), table(), table()
    bm = [[-1] * (n + 1) for _ in range(m + 1)]
    bv = [[-1] * (n + 1) for _ in range(m + 1)]
    bh = [[-1] * (n + 1) for _ in range(m + 1)]

    # 自由起点 S(i-1,0)=enc(0,0,i)：左后缀从 i 开始（1 起始），
    # 可向右走出 H（前导右空缺）或向右下走出 M。
    for i in range(1, m + 1):
        S[i - 1][0] = enc(0, 0, i)

    # a=0 行：从 S(0,0) 出发的连续前导右空缺，首列 -3、其后每列 -1
    for b in range(1, n + 1):
        H[0][b] = enc(GAP_OPEN + (b - 1) * GAP_EXTEND, 0, 1)
        bh[0][b] = ST_S if b == 1 else ST_H

    GO, GE = GAP_OPEN * POFF, GAP_EXTEND * POFF

    for a in range(1, m + 1):
        x = L[a - 1]
        Ma, Va, Ha, Sa = M[a], V[a], H[a], S[a]
        Mp, Vp, Hp, Sp = M[a - 1], V[a - 1], H[a - 1], S[a - 1]
        bma, bva, bha = bm[a], bv[a], bh[a]

        for b in range(1, n + 1):
            # ---- H(a,b)：空缺 - R[b]，前驱 (a,b-1) ----
            best, best_t = NEG, -1
            v = Ha[b - 1]
            if v != NEG:
                v += GE
                if v > best:
                    best, best_t = v, ST_H
            v = Ma[b - 1]
            if v != NEG:
                v += GO
                if v > best:
                    best, best_t = v, ST_M
            v = Va[b - 1]
            if v != NEG:
                v += GO
                if v > best:
                    best, best_t = v, ST_V
            v = Sa[b - 1]  # 仅 b==1 时可达
            if v != NEG:
                v += GO
                if v > best:
                    best, best_t = v, ST_S
            Ha[b] = best
            if best != NEG:
                bha[b] = best_t

            # ---- V(a,b)：L[a] - 空缺，前驱 (a-1,b) ----
            best, best_t = NEG, -1
            v = Vp[b]
            if v != NEG:
                v += GE
                if v > best:
                    best, best_t = v, ST_V
            v = Mp[b]
            if v != NEG:
                v += GO
                if v > best:
                    best, best_t = v, ST_M
            v = Hp[b]
            if v != NEG:
                v += GO
                if v > best:
                    best, best_t = v, ST_H
            if b == 1:
                v = Sp[0]  # S(a-1,0)：前导左空缺段首列
                if v != NEG:
                    v += GO
                    if v > best:
                        best, best_t = v, ST_S
            Va[b] = best
            if best != NEG:
                bva[b] = best_t

            # ---- M(a,b)：L[a] - R[b]，前驱 (a-1,b-1) ----
            y = R[b - 1]
            if x == UNKNOWN or y == UNKNOWN:
                delta = UNKNOWN_SCORE
            elif x == y:
                delta = MATCH_SCORE
            else:
                delta = MISMATCH_SCORE
            add = delta * POFF + IOFF  # 分数 +delta、字符对数 +1
            best, best_t = NEG, -1
            v = Mp[b - 1]
            if v != NEG:
                v += add
                if v > best:
                    best, best_t = v, ST_M
            v = Vp[b - 1]
            if v != NEG:
                v += add
                if v > best:
                    best, best_t = v, ST_V
            v = Hp[b - 1]
            if v != NEG:
                v += add
                if v > best:
                    best, best_t = v, ST_H
            v = Sp[b - 1]  # 仅 b==1 时可达
            if v != NEG:
                v += add
                if v > best:
                    best, best_t = v, ST_S
            Ma[b] = best
            if best != NEG:
                bma[b] = best_t

    # ---- 在 (m,j), j>=1 的结束状态中取字典序最优（且至少 1 对字符）----
    best = NEG
    end_b, end_state = 0, ST_M
    Mm, Vm, Hm = M[m], V[m], H[m]
    for b in range(1, n + 1):
        for v, t in ((Mm[b], ST_M), (Vm[b], ST_V), (Hm[b], ST_H)):
            if v == NEG or v <= best:
                continue
            z = v - BIAS
            rem = z - (z // POFF) * POFF
            if (rem + IOFF - 1) // IOFF >= 1:
                best, end_b, end_state = v, b, t

    if best == NEG:
        raise AlignmentError("无法产生至少含一对字符对齐的结果")

    # 解码：z = score*POFF + pairs*IOFF - start_i
    z = best - BIAS
    score_enc, rem = divmod(z, POFF)
    pairs = (rem + IOFF - 1) // IOFF
    start_i = pairs * IOFF - rem
    dp_score = score_enc

    # ---- 回溯，得到逆序原始列；进入 S 即结束 ----
    raw_cols: list[tuple[str, object, object]] = []
    a, b, state = m, end_b, end_state
    while True:
        if state == ST_M:
            p = bm[a][b]
            raw_cols.append(("M", L[a - 1], R[b - 1]))
            a -= 1
            b -= 1
        elif state == ST_V:
            p = bv[a][b]
            raw_cols.append(("V", L[a - 1], None))
            a -= 1
        else:
            p = bh[a][b]
            raw_cols.append(("H", None, R[b - 1]))
            b -= 1
        if p == ST_S:
            # S(a,b)=enc(0,0,i)，低项即 -i
            start_i = BIAS - S[a][b]
            break
        state = p

    raw_cols.reverse()

    # ---- 逐列计分（空缺段首列 -3、延续 -1）与拼接 ----
    columns = []
    merged_parts: list[str] = []
    conflicts = []
    substitutions = []
    unresolved = []
    li = start_i - 1  # 左段当前字符下标（0 起始）
    ri = 0           # 右段当前字符下标
    prev_gap = None  # 上一列空缺方向
    n_match = n_mismatch = n_unknown = 0
    n_gap_open = n_gap_ext = 0
    total = 0

    for ci, (kind, x, y) in enumerate(raw_cols, start=1):
        if kind == "M":
            lp, rp = li + 1, ri + 1
            prev_gap = None
            if x == UNKNOWN or y == UNKNOWN:
                col_score = UNKNOWN_SCORE
                n_unknown += 1
                if x == UNKNOWN and y != UNKNOWN:
                    merged = y
                    substitutions.append({
                        "column": ci,
                        "unknown_side": "left",
                        "unknown_pos": lp,
                        "known_side": "right",
                        "known_pos": rp,
                        "known_char": y,
                    })
                elif y == UNKNOWN and x != UNKNOWN:
                    merged = x
                    substitutions.append({
                        "column": ci,
                        "unknown_side": "right",
                        "unknown_pos": rp,
                        "known_side": "left",
                        "known_pos": lp,
                        "known_char": x,
                    })
                else:
                    merged = UNKNOWN
                    unresolved.append({"column": ci, "left_pos": lp, "right_pos": rp})
                col_type = "unknown"
            elif x == y:
                col_score = MATCH_SCORE
                n_match += 1
                merged = x
                col_type = "match"
            else:
                col_score = MISMATCH_SCORE
                n_mismatch += 1
                merged = x  # 异字保留左段字形
                conflicts.append({
                    "column": ci,
                    "left_pos": lp,
                    "left_char": x,
                    "right_pos": rp,
                    "right_char": y,
                })
                col_type = "mismatch"
            columns.append({
                "index": ci,
                "type": col_type,
                "score": col_score,
                "left_pos": lp,
                "left_char": x,
                "right_pos": rp,
                "right_char": y,
                "merged_char": merged,
            })
            merged_parts.append(merged)
            li += 1
            ri += 1
        elif kind == "V":
            if prev_gap == "V":
                col_score = GAP_EXTEND
                n_gap_ext += 1
            else:
                col_score = GAP_OPEN
                n_gap_open += 1
            prev_gap = "V"
            lp = li + 1
            columns.append({
                "index": ci,
                "type": "gap_left",
                "score": col_score,
                "left_pos": lp,
                "left_char": x,
                "right_pos": None,
                "right_char": None,
                "merged_char": x,
            })
            merged_parts.append(x)
            li += 1
        else:  # H
            if prev_gap == "H":
                col_score = GAP_EXTEND
                n_gap_ext += 1
            else:
                col_score = GAP_OPEN
                n_gap_open += 1
            prev_gap = "H"
            rp = ri + 1
            columns.append({
                "index": ci,
                "type": "gap_right",
                "score": col_score,
                "left_pos": None,
                "left_char": None,
                "right_pos": rp,
                "right_char": y,
                "merged_char": y,
            })
            merged_parts.append(y)
            ri += 1
        total += col_score

    if total != dp_score or pairs != n_match + n_mismatch + n_unknown:
        # 理论上不可达，属于算法内部错误
        raise AlignmentError("内部错误：计分校验失败")

    return {
        "score": total,
        "aligned_pairs": pairs,
        "score_breakdown": {
            "match": n_match,
            "mismatch": n_mismatch,
            "unknown": n_unknown,
            "gap_open": n_gap_open,
            "gap_extend": n_gap_ext,
        },
        "left_range": {
            "start": start_i,
            "end": m,
            "text": L[start_i - 1:],
        },
        "right_range": {
            "start": 1,
            "end": end_b,
            "text": R[:end_b],
        },
        "columns": columns,
        "merged_text": "".join(merged_parts),
        "conflicts": conflicts,
        "substitutions": substitutions,
        "unresolved_questions": unresolved,
    }
