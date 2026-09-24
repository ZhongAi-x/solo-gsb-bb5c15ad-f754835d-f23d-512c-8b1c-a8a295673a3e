"""古籍残页转写拼接 API。

提供 POST /align：提交左、右两段含 "?"（未辨认字）的转写文本，
返回最高分后缀-前缀对齐的原文区间、逐列对齐与拼接文本。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .aligner import AlignmentError, align

app = FastAPI(
    title="古籍残页转写拼接 API",
    version="1.0.0",
    description=(
        "将左段后缀与右段前缀进行带空缺罚分的对齐并拼接。"
        "相同字 +2，? 与任意字配对 0，异字 -2，"
        "连续空缺首字 -3、其余每字 -1。"
    ),
)


class AlignRequest(BaseModel):
    left: str = Field(
        ..., description="左段转写文本，含 '?' 表示未辨认字；仅其后缀参与对齐"
    )
    right: str = Field(
        ..., description="右段转写文本，含 '?' 表示未辨认字；仅其前缀参与对齐"
    )
    max_len: int | None = Field(
        default=None, ge=1, le=1000,
        description="单段最大字符数（默认 1000）",
    )
    require_question: bool = Field(
        default=True,
        description="是否要求两段文本均至少含一个 '?'（默认 true）",
    )


@app.exception_handler(AlignmentError)
async def alignment_error_handler(_request, exc: AlignmentError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
async def index():
    return {
        "service": "古籍残页转写拼接 API",
        "docs": "/docs",
        "endpoint": "POST /align",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/align", summary="提交两段文本，返回最优对齐与拼接")
async def do_align(req: AlignRequest):
    if req.require_question and ("?" not in req.left or "?" not in req.right):
        raise AlignmentError("两段文本均须至少包含一个 '?'（未辨认字）")
    if req.max_len is not None:
        result = align(req.left, req.right, max_len=req.max_len)
    else:
        result = align(req.left, req.right)
    return result
