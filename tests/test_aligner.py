"""核心算法测试。"""

import pytest

from app.aligner import AlignmentError, align


def test_unknown_replaced_by_known_right():
    # 左段前缀 "天" 不参与；后缀 "?下" 对齐右段前缀 "天下"
    r = align("天?下", "天下太平")
    assert r["score"] == 2
    assert r["aligned_pairs"] == 2
    assert r["left_range"] == {"start": 2, "end": 3, "text": "?下"}
    assert r["right_range"]["text"] == "天下"
    assert r["merged_text"] == "天下"
    assert r["substitutions"][0]["known_char"] == "天"
    assert r["substitutions"][0]["unknown_side"] == "left"
    assert r["conflicts"] == []


def test_tie_same_score_and_pairs_prefers_smaller_start():
    # 真实同分同对数（枚举核对）："甲乙丙丙"/"甲?"
    #   i=1,j=2：甲/甲 +2、乙空缺 -3、丙空缺 -1、丙/? 0 = -2 分 2 对
    #   i=3,j=2：丙/甲 -2、丙/? 0 = -2 分 2 对
    # 分数与字符对数均相同，取左段起点较小者 i=1。
    r = align("甲乙丙丙", "甲?")
    assert (r["score"], r["aligned_pairs"], r["left_range"]["start"]) == (-2, 2, 1)


def test_tie_same_score_prefers_more_pairs():
    # "丙丙乙丙"/"甲甲丙甲"：
    #   i=2：丙/甲-2、乙/甲-2、丙/丙+2 = -2 分 3 对
    #   i=4：甲空缺-3、甲空缺-1、丙/丙+2 = -2 分 1 对
    # 同分取字符对数更多者。
    r = align("丙丙乙丙", "甲甲丙甲")
    assert (r["score"], r["aligned_pairs"], r["left_range"]["start"]) == (-2, 3, 2)


def test_gap_run_open_then_extend():
    # L="丙丁"，R="乙甲丙丁"：右前缀内 "丙丁" 直配得 +4，
    # 前置两个连续空缺 -3,-1，总分 0，逐列为 -3,-1,+2,+2。
    # 更短前缀的对齐（如 丁/乙 等）均为负分，故最优必含该空缺段。
    r = align("丙丁", "乙甲丙丁")
    assert [c["score"] for c in r["columns"]] == [-3, -1, 2, 2]
    assert r["score"] == 0
    assert r["merged_text"] == "乙甲丙丁"


def test_higher_score_dominates_start_preference():
    # "甲乙乙"/"乙乙"：i=2 全匹配 +4，优于 i=1 的 0 分
    r = align("甲乙乙", "乙乙")
    assert (r["score"], r["aligned_pairs"], r["left_range"]["start"]) == (4, 2, 2)


def test_higher_score_beats_pair_count_and_start():
    # 仅末字 "丙" 与右段 "丙" 对齐得 +2，优于前缀含异字的对齐
    r = align("甲乙丙", "丙")
    assert r["score"] == 2
    assert r["left_range"]["start"] == 3
    assert r["merged_text"] == "丙"


def test_mismatch_keeps_left_char_and_lists_positions():
    r = align("甲乙", "甲丙")
    assert r["score"] == 0  # +2-2
    assert r["merged_text"] == "甲乙"
    assert r["conflicts"] == [{
        "column": 2,
        "left_pos": 2,
        "left_char": "乙",
        "right_pos": 2,
        "right_char": "丙",
    }]


def test_gap_affine_penalty_leading_right_gap():
    # 后缀 "丁" 对齐右段前缀 "乙丁"：空缺列 -3 + 匹配 +2 = -1
    r = align("丁", "乙丁")
    assert r["score"] == -1
    types = [c["type"] for c in r["columns"]]
    assert types == ["gap_right", "match"]
    assert [c["score"] for c in r["columns"]] == [-3, 2]
    assert r["merged_text"] == "乙丁"


def test_unknown_with_unknown_stays_unknown():
    r = align("?", "?")
    assert r["score"] == 0
    assert r["merged_text"] == "?"
    assert len(r["unresolved_questions"]) == 1


def test_unknown_replaced_from_left_when_right_unknown():
    r = align("甲", "?")
    assert r["merged_text"] == "甲"
    assert r["substitutions"][0]["unknown_side"] == "right"


def test_at_least_one_pair_required():
    # 纯空缺对齐恒为负分；仍能找到唯一的一对字符列（异字 -2）
    r = align("甲", "乙")
    assert r["score"] == -2
    assert r["aligned_pairs"] == 1


def test_empty_inputs_rejected():
    with pytest.raises(AlignmentError):
        align("甲", "  ")
    with pytest.raises(AlignmentError):
        align("", "乙")


def test_columns_scores_sum_to_total_and_merged_consistency():
    r = align("?甲乙天丙丁", "乙?天乙丙甲丁?")
    assert sum(c["score"] for c in r["columns"]) == r["score"]
    assert r["merged_text"] == "".join(c["merged_char"] for c in r["columns"])
    pairs = sum(1 for c in r["columns"] if c["type"] in
                ("match", "mismatch", "unknown"))
    assert pairs == r["aligned_pairs"]


def test_range_texts_are_suffix_and_prefix():
    left, right = "开篇甲乙丙", "乙丙后续文字"
    r = align(left, right)
    assert r["left_range"]["text"] == left[r["left_range"]["start"] - 1:]
    assert r["right_range"]["text"] == right[:r["right_range"]["end"]]


def test_same_score_tie_picks_smallest_start():
    # 分数优先：i=2 的 乙/乙 +2 优于 i=1 的 0 分两对，
    # 因此这里实际验证“高分优先于对数与起点”
    r = align("乙乙", "乙甲")
    assert r["score"] == 2
    assert r["left_range"]["start"] == 2
    assert r["aligned_pairs"] == 1


def test_double_unknown_and_conflict_together():
    # "?甲乙"/"?甲丙"：双 ? 保留 + 匹配 + 异字（保留左字并列冲突）
    r = align("?甲乙", "?甲丙")
    assert (r["score"], r["aligned_pairs"], r["left_range"]["start"]) == (0, 3, 1)
    assert r["merged_text"] == "?甲乙"
    assert len(r["unresolved_questions"]) == 1
    assert r["conflicts"][0]["left_char"] == "乙"
    assert r["conflicts"][0]["right_char"] == "丙"
    assert r["conflicts"][0]["left_pos"] == 3
    assert r["conflicts"][0]["right_pos"] == 3


def test_max_len_enforced():
    with pytest.raises(AlignmentError):
        align("甲" * 5, "乙", max_len=4)
