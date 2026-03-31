import streamlit as st
import pandas as pd
import datetime as dt
from dateutil.relativedelta import relativedelta
import plotly.express as px
import streamlit.components.v1 as components
import math

# =====================================================
# 临床研究智能管理工具（CRMS CRDN/SHAPE/CS Team V1.0）
# V1.11（修复Summary渲染bug，恢复摘要表正常显示）
# =====================================================

APP_TITLE = "临床研究智能管理工具（CRMS CRDN/SHAPE/CS Team V1.0）"
st.set_page_config(page_title=APP_TITLE, layout="wide")

# 标题允许自动换行，避免长标题被截断
st.markdown(
    f"""
    <h1 style='
        white-space: normal;
        word-break: break-word;
        margin: 0;
        padding: 0;
        font-size: 2rem;
        line-height: 1.25;
    '>{APP_TITLE}</h1>
    """,
    unsafe_allow_html=True
)

# ---------- UI Theme (light, clean, clinical) ----------
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1200px;}
    section[data-testid="stSidebar"] {background: #F6F7FB;}
    h1, h2, h3 {letter-spacing: -0.02em;}
    div[data-testid="stMetric"] {
        background: #FFFFFF;
        padding: 14px 14px;
        border-radius: 16px;
        border: 1px solid rgba(15, 23, 42, 0.08);
        box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
        min-height: 150px;
    }
    div[data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow-wrap: break-word;
        line-height: 1.25;
    }
    div[data-testid="stMetricValue"] {
        white-space: normal !important;
        overflow-wrap: anywhere;
        word-break: break-word !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.15;
        display: block !important;
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 1.7rem !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.15 !important;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 16px;
        border: 1px solid rgba(15, 23, 42, 0.08);
        overflow: hidden;
    }
    div[data-testid="stExpander"] details {
        border-radius: 16px;
        border: 1px solid rgba(15, 23, 42, 0.08);
        background: #FFFFFF;
    }
    /* dataframe number wrap */
    .stDataFrame [role="gridcell"] { white-space: nowrap; }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------ 通用工具 ------------------ #
USD_TO_RMB_DEFAULT = 7.0

PIE_COLOR_THEMES = {
    "蓝色系": ["#1D4ED8", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE", "#DBEAFE"],
    "青绿色系": ["#0F766E", "#14B8A6", "#2DD4BF", "#5EEAD4", "#99F6E4", "#CCFBF1"],
    "紫蓝系": ["#4338CA", "#6366F1", "#818CF8", "#A5B4FC", "#C7D2FE", "#E0E7FF"],
    "灰蓝系": ["#334155", "#475569", "#64748B", "#94A3B8", "#CBD5E1", "#E2E8F0"],
    "暖中性色": ["#7C6F64", "#A1887F", "#BCAAA4", "#D7CCC8", "#EDE0D4", "#F5EBE0"],
}

def get_color_sequence(theme_name: str, n: int) -> list:
    seq = PIE_COLOR_THEMES.get(theme_name, PIE_COLOR_THEMES["蓝色系"])
    if n <= len(seq):
        return seq[:n]
    return [seq[i % len(seq)] for i in range(n)]


def round1(x):
    try:
        return float(f"{float(x):.1f}")
    except Exception:
        return 0.0

def to_rmb(amount: float, currency: str, fx_usd_to_rmb: float) -> float:
    amount = float(amount or 0.0)
    if str(currency).upper() == "USD":
        return amount * float(fx_usd_to_rmb)
    return amount

def from_rmb(amount_rmb: float, currency: str, fx_usd_to_rmb: float) -> float:
    amount_rmb = float(amount_rmb or 0.0)
    if str(currency).upper() == "USD":
        return amount_rmb / float(fx_usd_to_rmb) if fx_usd_to_rmb else 0.0
    return amount_rmb

def fmt_money_full(x: float) -> str:
    # 完整数字展示（带千分位，保留1位小数）
    return f"{float(x):,.1f}"

def convert_rmb_to_currency(amount_rmb: float, currency: str, fx_usd_to_rmb: float) -> float:
    currency = str(currency).upper()
    if currency == "USD":
        return round1(float(amount_rmb or 0.0) / float(fx_usd_to_rmb)) if float(fx_usd_to_rmb) else 0.0
    return round1(amount_rmb)

def currency_symbol(currency: str) -> str:
    return "USD" if str(currency).upper() == "USD" else "RMB"

def fmt_metric_delta(amount_rmb: float, currency: str, fx_usd_to_rmb: float) -> str:
    shown = convert_rmb_to_currency(amount_rmb, currency, fx_usd_to_rmb)
    return f"≈ {fmt_money_full(shown)} {currency_symbol(currency)}"

def fmt_money_cn_rmb(amount_rmb: float) -> str:
    """
    仅用于RMB：返回“X百万X万”风格（尽量直观，非严格中文大写金额）。
    例：12,345,678 -> 12百万35万
    """
    a = float(amount_rmb or 0.0)
    if a <= 0:
        return "0"
    million = int(a // 1_000_000)
    ten_thousand = int((a - million * 1_000_000) // 10_000)
    parts = []
    if million > 0:
        parts.append(f"{million}百万")
    if ten_thousand > 0:
        parts.append(f"{ten_thousand}万")
    if not parts:
        parts.append("不足1万")
    return "".join(parts)

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return float(default)

def months_between(start: dt.date, end: dt.date) -> int:
    if end < start:
        start, end = end, start
    # 向上取整到“月”的粗略跨度
    m = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day >= start.day:
        m += 1
    return max(1, int(m))

def month_add(start_date: dt.date, offset_months: int) -> dt.date:
    month = start_date.month - 1 + int(offset_months)
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(
        start_date.day,
        [31,
         29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
         31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return dt.date(year, month, day)

def fiscal_quarter_label(date_obj: dt.date) -> str:
    # 5-7: FY(年+1)Q1; 8-10: FY(年+1)Q2; 11-1: FY(对应年)Q3; 2-4: FY(对应年)Q4
    m = date_obj.month
    fy_year = date_obj.year + 1 if m >= 5 else date_obj.year
    if 5 <= m <= 7:
        q = 1
    elif 8 <= m <= 10:
        q = 2
    elif m in (11, 12, 1):
        q = 3
    else:
        q = 4
    return f"FY{str(fy_year)[-2:]}Q{q}"

def build_quarter_labels_from_range(start_date: dt.date, end_date: dt.date):
    months = months_between(start_date, end_date)
    labels = []
    for i in range(months):
        d = month_add(start_date, i)
        q = fiscal_quarter_label(d)
        if q not in labels:
            labels.append(q)
    return labels

def allocate_budget_by_month_equal(total_rmb: float, start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    """按月份均匀分布 -> 汇总到FY季度"""
    m = months_between(start_date, end_date)
    if m <= 0 or total_rmb <= 0:
        return pd.DataFrame(columns=["季度", "费用_RMB"])
    per_m = total_rmb / m
    acc = {}
    for i in range(m):
        d = month_add(start_date, i)
        q = fiscal_quarter_label(d)
        acc[q] = acc.get(q, 0.0) + per_m
    data = [(k, round1(v)) for k, v in acc.items()]
    return pd.DataFrame(data, columns=["季度", "费用_RMB"])

def allocate_budget_by_fy_quarter_pattern(total_rmb: float, quarter_labels: list[str], fy_q_pcts: dict) -> pd.DataFrame:
    """
    按“财年季度比例（Q1-Q4）”在项目跨越的季度上分配：
    - 先给每个出现的季度一个权重（取该季度的Q#对应比例）
    - 再按权重归一化分配到每个季度
    """
    if total_rmb <= 0 or not quarter_labels:
        return pd.DataFrame(columns=["季度", "费用_RMB"])
    weights = []
    for qlab in quarter_labels:
        qnum = int(str(qlab).split("Q")[-1])
        weights.append(max(0.0, float(fy_q_pcts.get(qnum, 0.0))))
    s = sum(weights)
    if s <= 0:
        # fallback: 平均
        per = total_rmb / len(quarter_labels)
        return pd.DataFrame([(q, round1(per)) for q in quarter_labels], columns=["季度", "费用_RMB"])
    data = []
    for qlab, w in zip(quarter_labels, weights):
        data.append((qlab, round1(total_rmb * w / s)))
    return pd.DataFrame(data, columns=["季度", "费用_RMB"])


def parse_fy_quarter_label(label: str):
    s = str(label).upper().replace(" ", "")
    fy_part = s.split("Q")[0].replace("FY", "")
    q_part = s.split("Q")[-1]
    try:
        fy = int(fy_part)
        q = int(q_part)
        return fy, q
    except Exception:
        return None, None


def make_fyq_label(fy, q):
    fy = int(fy)
    q = int(q)
    return f"FY{fy}Q{q}"


def build_default_cashflow_editor_df(start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    quarter_labels = build_quarter_labels_from_range(start_date, end_date)
    rows = []
    if len(quarter_labels) == 0:
        return pd.DataFrame(columns=["财年", "季度", "占比(%)"])

    pct = round(100.0 / len(quarter_labels), 2)
    for lab in quarter_labels:
        fy, q = parse_fy_quarter_label(lab)
        if fy is not None and q is not None:
            rows.append({"财年": fy, "季度": q, "占比(%)": pct})

    return pd.DataFrame(rows, columns=["财年", "季度", "占比(%)"])


def allocate_budget_by_custom_fyq_table(total_rmb: float, fyq_df: pd.DataFrame) -> pd.DataFrame:
    if total_rmb <= 0 or fyq_df is None or fyq_df.empty:
        return pd.DataFrame(columns=["财年", "Q", "季度", "占比(%)", "费用_RMB"])

    df = fyq_df.copy()
    df["财年"] = pd.to_numeric(df["财年"], errors="coerce")
    df["季度"] = pd.to_numeric(df["季度"], errors="coerce")
    df["占比(%)"] = pd.to_numeric(df["占比(%)"], errors="coerce")
    df = df.dropna(subset=["财年", "季度", "占比(%)"]).copy()
    df["财年"] = df["财年"].astype(int)
    df["季度"] = df["季度"].astype(int)
    df = df[df["季度"].isin([1, 2, 3, 4])].copy()
    df["占比(%)"] = df["占比(%)"].clip(lower=0)

    if df.empty:
        return pd.DataFrame(columns=["财年", "Q", "季度", "占比(%)", "费用_RMB"])

    df = (
        df.groupby(["财年", "季度"], as_index=False)["占比(%)"]
        .sum()
        .sort_values(["财年", "季度"])
        .reset_index(drop=True)
    )

    total_pct = df["占比(%)"].sum()
    if total_pct <= 0:
        df["占比(%)"] = 100.0 / len(df)
        total_pct = 100.0

    df["费用_RMB"] = df["占比(%)"].apply(lambda x: round1(total_rmb * x / total_pct))
    df["Q"] = df["季度"].apply(lambda x: f"Q{x}")
    df["季度"] = df.apply(lambda r: make_fyq_label(r["财年"], r["季度"]), axis=1)

    return df[["财年", "Q", "季度", "占比(%)", "费用_RMB"]]


def format_fu_years_text(months: int) -> str:
    months = int(months or 0)
    if months % 12 == 0 and months > 0:
        years = months // 12
        return f"{years} Years"
    return f"{months} Months"


def format_endpoint_text(months: int) -> str:
    months = int(months or 0)
    if months % 12 == 0 and months > 0:
        years = months // 12
        return f"{years}Y"
    return f"{months}M"


# ------------------ 预算明细构建 ------------------ #
def add_cost_item(rows, category, item_name, unit_price_input, qty, remark, input_currency, fx_usd_to_rmb, show_both):
    qty = float(qty or 0.0)
    unit_price_input = float(unit_price_input or 0.0)

    unit_price_rmb = to_rmb(unit_price_input, input_currency, fx_usd_to_rmb)
    subtotal_rmb = round1(unit_price_rmb * qty)
    if subtotal_rmb == 0:
        return 0.0

    row = {
        "预算模块": category,
        "费用项目": item_name,
        f"单价 ({input_currency})": round1(unit_price_input),
        "数量": round1(qty),
        f"小计 ({input_currency})": round1(from_rmb(subtotal_rmb, input_currency, fx_usd_to_rmb)),
        "备注": remark or "",
    }
    if show_both:
        other = "USD" if str(input_currency).upper() == "RMB" else "RMB"
        row[f"折算单价 ({other})"] = round1(from_rmb(unit_price_rmb, other, fx_usd_to_rmb))
        row[f"折算小计 ({other})"] = round1(from_rmb(subtotal_rmb, other, fx_usd_to_rmb))

    rows.append(row)
    return subtotal_rmb




def month_range_starts(start_date: dt.date, end_date: dt.date):
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    cur = dt.date(start_date.year, start_date.month, 1)
    end_month = dt.date(end_date.year, end_date.month, 1)
    out = []
    while cur <= end_month:
        out.append(cur)
        cur = (cur + relativedelta(months=+1)).replace(day=1)
    return out


def build_timeline_lookup(df_timeline: pd.DataFrame):
    lookup = {"level1": {}, "level2": {}}
    if df_timeline is None or df_timeline.empty:
        return lookup
    tmp = df_timeline.copy()
    tmp["开始日期"] = pd.to_datetime(tmp["开始日期"])
    tmp["结束日期"] = pd.to_datetime(tmp["结束日期"])
    for lvl1, g in tmp.groupby("阶段"):
        lookup["level1"][lvl1] = {
            "start": g["开始日期"].min().date(),
            "end": g["结束日期"].max().date(),
        }
    for _, r in tmp.iterrows():
        lookup["level2"][r["子任务"]] = {
            "level1": r["阶段"],
            "start": pd.to_datetime(r["开始日期"]).date(),
            "end": pd.to_datetime(r["结束日期"]).date(),
        }
    return lookup


def get_phase_range(timeline_lookup, level1=None, level2=None, fallback_start=None, fallback_end=None):
    if level2 and level2 in timeline_lookup.get("level2", {}):
        rec = timeline_lookup["level2"][level2]
        return rec["start"], rec["end"]
    if level1 and level1 in timeline_lookup.get("level1", {}):
        rec = timeline_lookup["level1"][level1]
        return rec["start"], rec["end"]
    return fallback_start, fallback_end


def allocate_lump_sum(amount_rmb: float, at_date: dt.date, label: str) -> pd.DataFrame:
    if amount_rmb <= 0 or at_date is None:
        return pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段"])
    return pd.DataFrame([{
        "月份": dt.date(at_date.year, at_date.month, 1),
        "费用_RMB": float(amount_rmb),
        "预算阶段": label,
    }])


def allocate_spread(amount_rmb: float, start_date: dt.date, end_date: dt.date, label: str) -> pd.DataFrame:
    months = month_range_starts(start_date, end_date)
    if amount_rmb <= 0 or not months:
        return pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段"])
    per_m = float(amount_rmb) / len(months)
    return pd.DataFrame([{
        "月份": m,
        "费用_RMB": per_m,
        "预算阶段": label,
    } for m in months])


def allocate_weighted_phases(amount_rmb: float, phase_specs: list, timeline_lookup, fallback_start: dt.date, fallback_end: dt.date) -> pd.DataFrame:
    frames = []
    total_w = sum(max(0.0, float(x.get("weight", 0.0))) for x in phase_specs)
    if amount_rmb <= 0 or total_w <= 0:
        return pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段"])
    for spec in phase_specs:
        w = max(0.0, float(spec.get("weight", 0.0)))
        if w <= 0:
            continue
        mode = spec.get("mode", "spread")
        lvl1 = spec.get("level1")
        lvl2 = spec.get("level2")
        s, e = get_phase_range(timeline_lookup, lvl1, lvl2, fallback_start, fallback_end)
        label = lvl2 or lvl1 or "未映射阶段"
        sub_amt = float(amount_rmb) * w / total_w
        if mode == "lump_start":
            frames.append(allocate_lump_sum(sub_amt, s, label))
        elif mode == "lump_end":
            frames.append(allocate_lump_sum(sub_amt, e, label))
        else:
            frames.append(allocate_spread(sub_amt, s, e, label))
    if not frames:
        return pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段"])
    return pd.concat(frames, ignore_index=True)


BUDGET_ALLOCATION_RULES = {
    "研究者筛选费": {"phases": [{"level1": "患者入组", "level2": "受试者入组", "weight": 1.0, "mode": "spread"}]},
    "研究者手术费": {"phases": [{"level1": "患者入组", "level2": "受试者入组", "weight": 1.0, "mode": "spread"}]},
    "筛选失败费用": {"phases": [{"level1": "患者入组", "level2": "受试者入组", "weight": 1.0, "mode": "spread"}]},
    "受试者补偿": {"phases": [{"level1": "患者入组", "weight": 0.4}, {"level1": "患者随访", "weight": 0.6}]},
    "受试者检查费用": {"phases": [{"level1": "患者入组", "weight": 0.35}, {"level1": "患者随访", "weight": 0.65}]},
    "组长单位费用": {"phases": [{"level1": "研究中心启动", "level2": "组长单位启动", "weight": 1.0, "mode": "lump_start"}]},
    "EC/Clinical Institute Process费用": {"phases": [{"level1": "GCP&伦理提交", "weight": 0.8}, {"level1": "研究中心启动", "weight": 0.2}]},
    "中心管理费用": {"phases": [{"level1": "患者入组", "weight": 0.45}, {"level1": "患者随访", "weight": 0.35}, {"level1": "数据分析", "weight": 0.20}]},
    "Site税费": {"phases": [{"level1": "患者入组", "weight": 0.45}, {"level1": "患者随访", "weight": 0.35}, {"level1": "数据分析", "weight": 0.20}]},
    "CRC费用": {"phases": [{"level1": "研究中心启动", "weight": 0.10}, {"level1": "患者入组", "weight": 0.50}, {"level1": "患者随访", "weight": 0.30}, {"level1": "数据分析", "weight": 0.10}]},
    "PM费用": {"phases": [{"level1": "研究准备阶段", "weight": 0.10}, {"level1": "研究文件准备", "weight": 0.15}, {"level1": "GCP&伦理提交", "weight": 0.10}, {"level1": "研究中心启动", "weight": 0.10}, {"level1": "患者入组", "weight": 0.25}, {"level1": "患者随访", "weight": 0.15}, {"level1": "数据分析", "weight": 0.10}, {"level1": "研究结束", "weight": 0.05}]},
    "Monitor费用": {"phases": [{"level1": "研究中心启动", "weight": 0.20}, {"level1": "患者入组", "weight": 0.45}, {"level1": "患者随访", "weight": 0.25}, {"level1": "研究结束", "weight": 0.10}]},
    "DM费用": {"phases": [{"level1": "研究文件准备", "weight": 0.25}, {"level1": "患者入组", "weight": 0.15}, {"level1": "患者随访", "weight": 0.20}, {"level1": "数据分析", "weight": 0.40}]},
    "Safety费用": {"phases": [{"level1": "患者入组", "weight": 0.30}, {"level1": "患者随访", "weight": 0.45}, {"level1": "数据分析", "weight": 0.25}]},
    "EDC系统费用": {"phases": [{"level1": "研究文件准备", "weight": 0.35}, {"level1": "患者入组", "weight": 0.20}, {"level1": "患者随访", "weight": 0.20}, {"level1": "数据分析", "weight": 0.25}]},
    "翻译/打印费用": {"phases": [{"level1": "研究文件准备", "weight": 0.75}, {"level1": "研究结束", "weight": 0.25}]},
    "保险费用": {"phases": [{"level1": "研究中心启动", "weight": 1.0, "mode": "lump_start"}]},
    "数据分析费用": {"phases": [{"level1": "数据分析", "weight": 1.0}]},
    "中心实验室费用": {"phases": [{"level1": "患者入组", "weight": 0.25}, {"level1": "患者随访", "weight": 0.75}]},
    "CEC费用": {"phases": [{"level1": "患者随访", "weight": 1.0}]},
    "Travel费用": {"phases": [{"level1": "研究中心启动", "weight": 0.30}, {"level1": "患者入组", "weight": 0.40}, {"level1": "患者随访", "weight": 0.30}]},
    "Recording费用": {"phases": [{"level1": "患者入组", "weight": 0.50}, {"level1": "患者随访", "weight": 0.50}]},
    "研究者会费用": {"phases": [{"level1": "研究准备阶段", "level2": "研究者会议", "weight": 1.0, "mode": "lump_start"}]},
    "Vendor税费": {"phases": [{"level1": "研究准备阶段", "weight": 0.10}, {"level1": "研究文件准备", "weight": 0.10}, {"level1": "研究中心启动", "weight": 0.10}, {"level1": "患者入组", "weight": 0.30}, {"level1": "患者随访", "weight": 0.20}, {"level1": "数据分析", "weight": 0.15}, {"level1": "研究结束", "weight": 0.05}]},
    "产品运输费用": {"phases": [{"level1": "研究准备阶段", "level2": "产品运输及相关管理流程准备", "weight": 0.30}, {"level1": "患者入组", "weight": 0.70}]},
    "仓储费用": {"phases": [{"level1": "患者入组", "weight": 0.45}, {"level1": "患者随访", "weight": 0.55}]},
    "产品成本": {"phases": [{"level1": "患者入组", "weight": 1.0}]},
    "项目经理FTE费用": {"phases": [{"level1": "研究准备阶段", "weight": 0.12}, {"level1": "研究文件准备", "weight": 0.12}, {"level1": "GCP&伦理提交", "weight": 0.08}, {"level1": "研究中心启动", "weight": 0.10}, {"level1": "患者入组", "weight": 0.25}, {"level1": "患者随访", "weight": 0.18}, {"level1": "数据分析", "weight": 0.10}, {"level1": "研究结束", "weight": 0.05}]},
    "CRA费用": {"phases": [{"level1": "研究中心启动", "weight": 0.20}, {"level1": "患者入组", "weight": 0.40}, {"level1": "患者随访", "weight": 0.30}, {"level1": "研究结束", "weight": 0.10}]},
    "MCRS费用": {"phases": [{"level1": "患者入组", "weight": 0.45}, {"level1": "患者随访", "weight": 0.45}, {"level1": "数据分析", "weight": 0.10}]},
    "Global team费用": {"phases": [{"level1": "研究准备阶段", "weight": 0.10}, {"level1": "研究文件准备", "weight": 0.10}, {"level1": "GCP&伦理提交", "weight": 0.10}, {"level1": "研究中心启动", "weight": 0.10}, {"level1": "患者入组", "weight": 0.25}, {"level1": "患者随访", "weight": 0.15}, {"level1": "数据分析", "weight": 0.10}, {"level1": "研究结束", "weight": 0.10}]},
}


def allocate_budget_item_by_timeline(row: dict, timeline_lookup, fallback_start: dt.date, fallback_end: dt.date) -> pd.DataFrame:
    item = str(row.get("费用项目", "")).strip()
    amount_rmb = float(row.get("金额_RMB", 0.0) or 0.0)
    if amount_rmb <= 0:
        return pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段", "费用项目", "预算模块"])

    if item.startswith("研究者随访费 -"):
        alloc = allocate_weighted_phases(amount_rmb, [{"level1": "患者随访", "weight": 1.0}], timeline_lookup, fallback_start, fallback_end)
    else:
        rule = BUDGET_ALLOCATION_RULES.get(item)
        if rule is None:
            alloc = allocate_spread(amount_rmb, fallback_start, fallback_end, "全项目周期")
        else:
            alloc = allocate_weighted_phases(amount_rmb, rule.get("phases", []), timeline_lookup, fallback_start, fallback_end)

    if alloc.empty:
        alloc = allocate_spread(amount_rmb, fallback_start, fallback_end, "全项目周期")
    alloc["费用项目"] = item
    alloc["预算模块"] = str(row.get("预算模块", ""))
    return alloc


def build_smart_cashflow(rows: list, df_timeline: pd.DataFrame, start_date: dt.date, end_date: dt.date) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not rows:
        empty_q = pd.DataFrame(columns=["财年", "Q", "季度", "占比(%)", "费用_RMB"])
        empty_m = pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段", "费用项目", "预算模块"])
        return empty_q, empty_m
    timeline_lookup = build_timeline_lookup(df_timeline)
    budget_df = pd.DataFrame(rows).copy()
    amount_col = [c for c in budget_df.columns if c.startswith("小计 (")][0]
    budget_df[amount_col] = pd.to_numeric(budget_df[amount_col], errors="coerce").fillna(0)
    currency = amount_col.replace("小计 (", "").replace(")", "")
    budget_df["金额_RMB"] = budget_df[amount_col].apply(lambda x: round1(to_rmb(x, currency, fx_usd_to_rmb)))

    month_frames = []
    for _, r in budget_df.iterrows():
        month_frames.append(allocate_budget_item_by_timeline(r.to_dict(), timeline_lookup, start_date, end_date))
    month_df = pd.concat(month_frames, ignore_index=True) if month_frames else pd.DataFrame(columns=["月份", "费用_RMB", "预算阶段", "费用项目", "预算模块"])
    if month_df.empty:
        empty_q = pd.DataFrame(columns=["财年", "Q", "季度", "占比(%)", "费用_RMB"])
        return empty_q, month_df

    month_df["月份"] = pd.to_datetime(month_df["月份"])
    month_df = month_df.groupby(["月份", "预算阶段", "费用项目", "预算模块"], as_index=False)["费用_RMB"].sum()
    month_df["财年季度"] = month_df["月份"].dt.date.apply(fiscal_quarter_label)
    q_df = month_df.groupby("财年季度", as_index=False)["费用_RMB"].sum()
    q_df["财年"] = q_df["财年季度"].apply(lambda x: parse_fy_quarter_label(x)[0])
    q_df["Q"] = q_df["财年季度"].apply(lambda x: f"Q{parse_fy_quarter_label(x)[1]}")
    q_df = q_df.sort_values(["财年", "Q"]).reset_index(drop=True)
    total = max(1e-9, q_df["费用_RMB"].sum())
    q_df["占比(%)"] = q_df["费用_RMB"] / total * 100
    q_df["季度"] = q_df["财年季度"]
    return q_df[["财年", "Q", "季度", "占比(%)", "费用_RMB"]], month_df


# ------------------ session ------------------ #
if "generated" not in st.session_state:
    st.session_state.generated = False

# =====================================================
# Sidebar：项目配置
# =====================================================
st.sidebar.header("项目基本信息")

project_name = st.sidebar.text_input("项目名称", value="示例项目")
study_type = st.sidebar.selectbox("临床研究类型", ["上市前临床研究", "上市后临床研究", "ERP", "回顾性分析"])

st.sidebar.subheader("研究规模")
site_number = st.sidebar.number_input("中心数量", min_value=1, step=1, value=10)
n_planned = st.sidebar.number_input("计划入组例数 (n)", min_value=1, step=1, value=150)
n_lost = st.sidebar.number_input("预估失访例数", min_value=0, step=1, value=0)
n_screen_fail = st.sidebar.number_input("预估筛选失败例数", min_value=0, step=1, value=10)

st.sidebar.subheader("研究时间")
start_date = st.sidebar.date_input("研究开始时间", dt.date.today())

# 新增：用户自填参数
project_planned_duration_months = st.sidebar.number_input("项目预计持续时间（月）", min_value=1, step=1, value=36)
primary_endpoint_time_months = st.sidebar.number_input("主要终点时间（月，自研究开始起）", min_value=0, step=1, value=12)

# =====================================================
# Timeline：按一级/二级标签管理
# =====================================================
st.sidebar.markdown("---")
st.sidebar.subheader("项目时间线预估")

TIMELINE_TEMPLATE = {
    "研究准备阶段": [
        "项目立项",
        "研究中心名单提名、筛选及访视",
        "产品及人员培训",
        "供应商筛选与确认",
        "产品运输及相关管理流程准备",
        "研究者会议",
    ],
    "研究文件准备": [
        "研究方案撰写及获批",
        "CRF及数据库建立",
        "知情同意书",
        "研究计划书（监查计划、数据管理计划、统计分析计划等）",
        "其他相关表格及物料（受试者日记卡、招募海报、标签等）",
        "文件翻译",
    ],
    "GCP&伦理提交": [
        "GCP申请",
        "组长单位EC申请及获批",
        "其他中心EC申请及获批",
    ],
    "合同签署": [
        "合同起草与协商",
        "合同签字与盖章",
    ],
    "政府部门备案": [
        "上海药监局备案",
        "人类遗传办提交",
        "人类遗传办获批",
    ],
    "研究中心启动": [
        "组长单位启动",
        "其他中心启动",
    ],
    "患者入组": [
        "组长单位首例入组",
        "其他中心首例入组",
        "受试者入组",
        "末例入组",
    ],
    "患者随访": [
        "主要终点随访",
        "其他随访",
        "末例受试者末次访视",
    ],
    "数据分析": [
        "主要终点数据库锁定",
        "主要终点TLG/统计报告撰写",
        "主要终点临床研究报告撰写",
        "主要终点数据的监管提交",
        "数据库清理与锁定",
        "最终图表TLG/统计报告完成",
        "临床研究报告撰写",
    ],
    "研究结束": [
        "中心关闭访视",
        "临床研究报告的监管递交",
    ],
}

DEFAULT_ITEM_MONTHS = {
    "项目立项": 1,
    "研究中心名单提名、筛选及访视": 2,
    "产品及人员培训": 1,
    "供应商筛选与确认": 1,
    "产品运输及相关管理流程准备": 1,
    "研究者会议": 1,
    "研究方案撰写及获批": 3,
    "CRF及数据库建立": 2,
    "知情同意书": 2,
    "研究计划书（监查计划、数据管理计划、统计分析计划等）": 2,
    "其他相关表格及物料（受试者日记卡、招募海报、标签等）": 2,
    "文件翻译": 1,
    "GCP申请": 1,
    "组长单位EC申请及获批": 2,
    "其他中心EC申请及获批": 3,
    "合同起草与协商": 2,
    "合同签字与盖章": 1,
    "上海药监局备案": 1,
    "人类遗传办提交": 1,
    "人类遗传办获批": 3,
    "组长单位启动": 1,
    "其他中心启动": 2,
    "组长单位首例入组": 1,
    "其他中心首例入组": 2,
    "受试者入组": 12,
    "末例入组": 1,
    "主要终点随访": 12,
    "其他随访": 12,
    "末例受试者末次访视": 1,
    "主要终点数据库锁定": 1,
    "主要终点TLG/统计报告撰写": 2,
    "主要终点临床研究报告撰写": 2,
    "主要终点数据的监管提交": 1,
    "数据库清理与锁定": 2,
    "最终图表TLG/统计报告完成": 2,
    "临床研究报告撰写": 3,
    "中心关闭访视": 1,
    "临床研究报告的监管递交": 1,
}

LEVEL1_ORDER = list(TIMELINE_TEMPLATE.keys())
ITEM_TO_LEVEL1 = {item: lvl1 for lvl1, items in TIMELINE_TEMPLATE.items() for item in items}
LEVEL1_ORDER_INDEX = {name: i for i, name in enumerate(LEVEL1_ORDER)}
LEVEL2_ORDER_INDEX = {item: i for i, item in enumerate([x for lvl in LEVEL1_ORDER for x in TIMELINE_TEMPLATE[lvl]])}

def estimate_enroll_months(n_planned: int, site_number: int, rate: float) -> int:
    sites = max(1, int(site_number))
    rate = max(0.0001, float(rate))
    return max(1, int(math.ceil(float(n_planned) / (sites * rate))))

enroll_months_est = estimate_enroll_months(int(n_planned), int(site_number), 0.30)

sequential_defaults = {}
cur = start_date
for lvl1 in LEVEL1_ORDER:
    for item in TIMELINE_TEMPLATE[lvl1]:
        dur_m = int(DEFAULT_ITEM_MONTHS.get(item, 1))
        if item == "受试者入组":
            dur_m = enroll_months_est
        if item in ["主要终点随访", "其他随访"]:
            dur_m = max(1, int(project_planned_duration_months // 3))
        s = cur
        e = (cur + relativedelta(months=+dur_m)) - relativedelta(days=1)
        sequential_defaults[item] = (s, e)
        cur = e + relativedelta(days=1)

if "timeline_item_state" not in st.session_state:
    st.session_state.timeline_item_state = {
        item: {
            "enabled": True,
            "start": sequential_defaults[item][0],
            "end": sequential_defaults[item][1],
        }
        for item in sequential_defaults
    }

def reset_timeline_defaults():
    st.session_state.timeline_item_state = {
        item: {
            "enabled": True,
            "start": sequential_defaults[item][0],
            "end": sequential_defaults[item][1],
        }
        for item in sequential_defaults
    }

with st.sidebar.expander("Timeline 设置（按一级标签展开二级事项）", expanded=True):
    st.caption("勾选需要纳入时间线的二级事项，并用日历分别设置开始/结束日期。右侧将同步生成“项目阶段时间预估”和“项目阶段时间预估（详细）”。")
    if st.button("重置 Timeline 默认日期", key="reset_timeline_defaults_btn"):
        reset_timeline_defaults()

    for lvl1 in LEVEL1_ORDER:
        with st.expander(lvl1, expanded=False):
            for item in TIMELINE_TEMPLATE[lvl1]:
                state = st.session_state.timeline_item_state[item]
                checked = st.checkbox(item, value=state["enabled"], key=f"timeline_enable_{item}")
                c1, c2 = st.columns(2)
                s = c1.date_input("开始", value=state["start"], key=f"timeline_start_{item}")
                e = c2.date_input("结束", value=state["end"], key=f"timeline_end_{item}")
                if e < s:
                    st.warning(f"【{item}】结束日期早于开始日期，系统已自动调整为开始日期。")
                    e = s
                st.session_state.timeline_item_state[item] = {
                    "enabled": checked,
                    "start": s,
                    "end": e,
                }

phase_date_inputs = []
for item, cfg in st.session_state.timeline_item_state.items():
    if cfg["enabled"]:
        phase_date_inputs.append({
            "阶段": ITEM_TO_LEVEL1[item],
            "子任务": item,
            "类别": ITEM_TO_LEVEL1[item],
            "开始日期": cfg["start"],
            "结束日期": cfg["end"],
        })

followup_visit_rows = []

# =====================================================
# Budget：币种与模块
# =====================================================
st.sidebar.markdown("---")
st.sidebar.subheader("预算币种与汇率")
input_currency = st.sidebar.selectbox("输入/展示币种", ["RMB", "USD"], index=0)
fx_usd_to_rmb = st.sidebar.number_input("汇率（1 USD = ? RMB）", min_value=0.01, value=float(USD_TO_RMB_DEFAULT), step=0.1, format="%.2f")
show_both_currency = st.sidebar.checkbox("预算表同时显示折算币种", value=True)

st.sidebar.subheader("图表配色")
pie_color_theme = st.sidebar.selectbox("饼状图配色方案", list(PIE_COLOR_THEMES.keys()), index=0)

rows = []

# ------------------ 预算模块1：研究中心花费 ------------------ #
site_total_rmb = 0.0
with st.sidebar.expander("预算模块1：研究中心花费", expanded=True):
    if st.checkbox("研究者筛选费", value=True):
        unit = st.number_input("研究者筛选费 单价/例", min_value=0.0, step=100.0, value=500.0, key="site_screen_u")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "研究者筛选费", unit, n_planned, "单价*入组例数", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("研究者手术费", value=True):
        unit = st.number_input("研究者手术费 单价/例", min_value=0.0, step=100.0, value=5000.0, key="site_proc_u")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "研究者手术费", unit, n_planned, "单价*入组例数", input_currency, fx_usd_to_rmb, show_both_currency)

    st.markdown("#### 随访方式计费（按访视拆分）")
    use_visit_breakdown = st.checkbox("启用“按访视拆分计费”", value=True, key="site_visit_break")
    if use_visit_breakdown:
        default_visits = pd.DataFrame([
            {"访视名称": "V1", "每例次数": 1, "单价/次": 300.0},
            {"访视名称": "V2", "每例次数": 1, "单价/次": 300.0},
            {"访视名称": "V3", "每例次数": 1, "单价/次": 300.0},
        ])
        visits_df = st.data_editor(default_visits, use_container_width=True, num_rows="dynamic", key="visits_df")
        for _, r in visits_df.iterrows():
            name = str(r.get("访视名称", "")).strip()
            times = safe_float(r.get("每例次数", 0), 0)
            unit = safe_float(r.get("单价/次", 0), 0)
            if name and times > 0 and unit > 0:
                qty = float(n_planned) * float(times)
                site_total_rmb += add_cost_item(
                    rows, "预算模块1：研究中心花费",
                    f"研究者随访费 - {name}",
                    unit, qty,
                    "单价/次 * 每例次数 * 入组例数",
                    input_currency, fx_usd_to_rmb, show_both_currency
                )

    if st.checkbox("筛选失败费用", value=True):
        unit = st.number_input("筛选失败费用 单价/例", min_value=0.0, step=50.0, value=300.0, key="site_sf_u")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "筛选失败费用", unit, n_screen_fail, "单价*筛选失败例数", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("受试者补偿", value=True):
        unit = st.number_input("受试者补偿 单价/例", min_value=0.0, step=50.0, value=1000.0, key="site_comp_u")
        n_subj = st.number_input("受试者补偿 受试者数量", min_value=0, step=1, value=n_planned, key="site_comp_n")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "受试者补偿", unit, n_subj, "单价*受试者数量", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("受试者检查费用", value=True):
        unit = st.number_input("受试者检查费用 单价/例", min_value=0.0, step=50.0, value=2000.0, key="site_exam_u")
        n_exam = st.number_input("受试者检查费用 受检人数", min_value=0, step=1, value=n_planned, key="site_exam_n")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "受试者检查费用", unit, n_exam, "单价*受检人数", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("组长单位费用", value=True):
        amount = st.number_input("组长单位费用 金额", min_value=0.0, step=10000.0, value=200000.0, key="site_lead_a")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "组长单位费用", amount, 1, "", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("EC/Clinical Institute Process费用", value=True):
        unit = st.number_input("EC/Institute 平均费用/中心", min_value=0.0, step=1000.0, value=10000.0, key="site_ec_u")
        site_total_rmb += add_cost_item(rows, "预算模块1：研究中心花费", "EC/Clinical Institute Process费用", unit, site_number, "单价*中心数量", input_currency, fx_usd_to_rmb, show_both_currency)

    st.markdown("---")
    site_mgmt_rate = st.number_input("中心管理费用率（%）", min_value=0.0, step=1.0, value=25.0, key="site_mgmt_r")
    site_mgmt_fee_rmb = round1(site_total_rmb * site_mgmt_rate / 100.0)
    if site_mgmt_fee_rmb > 0:
        site_total_rmb += add_cost_item(
            rows, "预算模块1：研究中心花费", "中心管理费用",
            from_rmb(site_mgmt_fee_rmb, input_currency, fx_usd_to_rmb), 1,
            f"费率 {site_mgmt_rate:.1f}%",
            input_currency, fx_usd_to_rmb, show_both_currency
        )

    site_tax_rate = st.number_input("Site税费税率（%）", min_value=0.0, step=1.0, value=6.0, key="site_tax_r")
    site_tax_rmb = round1(site_total_rmb * site_tax_rate / 100.0)
    if site_tax_rmb > 0:
        site_total_rmb += add_cost_item(
            rows, "预算模块1：研究中心花费", "Site税费",
            from_rmb(site_tax_rmb, input_currency, fx_usd_to_rmb), 1,
            f"税率 {site_tax_rate:.1f}%",
            input_currency, fx_usd_to_rmb, show_both_currency
        )

# ------------------ 预算模块2：Vendor 花费 ------------------ #
vendor_total_rmb = 0.0
with st.sidebar.expander("预算模块2：Vendor 花费", expanded=False):

    def add_hourly_block(label, default_hours, default_rate):
        if st.checkbox(label, value=True, key=f"v_{label}_cb"):
            hours = st.number_input(f"{label} 工作总时间 (h)", min_value=0.0, step=1.0, value=float(default_hours), format="%.1f", key=f"v_{label}_h")
            rate = st.number_input(f"{label} 每小时费用", min_value=0.0, step=50.0, value=float(default_rate), key=f"v_{label}_r")
            return add_cost_item(rows, "预算模块2：Vendor 花费", label, rate, hours, "工作总时间(h)*每小时费用", input_currency, fx_usd_to_rmb, show_both_currency)
        return 0.0

    vendor_total_rmb += add_hourly_block("CRC费用", 200.0, 300.0)
    vendor_total_rmb += add_hourly_block("PM费用", 150.0, 400.0)
    vendor_total_rmb += add_hourly_block("Monitor费用", 300.0, 350.0)
    vendor_total_rmb += add_hourly_block("DM费用", 150.0, 300.0)
    vendor_total_rmb += add_hourly_block("Safety费用", 80.0, 350.0)

    def add_amount_block(label, default_amount):
        if st.checkbox(label, value=True, key=f"v_{label}_cb2"):
            amount = st.number_input(f"{label} 金额", min_value=0.0, step=10000.0, value=float(default_amount), key=f"v_{label}_a")
            return add_cost_item(rows, "预算模块2：Vendor 花费", label, amount, 1, "", input_currency, fx_usd_to_rmb, show_both_currency)
        return 0.0

    vendor_total_rmb += add_amount_block("EDC系统费用", 200000.0)
    vendor_total_rmb += add_amount_block("翻译/打印费用", 50000.0)
    vendor_total_rmb += add_amount_block("保险费用", 80000.0)
    vendor_total_rmb += add_amount_block("数据分析费用", 150000.0)
    vendor_total_rmb += add_amount_block("中心实验室费用", 100000.0)
    vendor_total_rmb += add_amount_block("CEC费用", 120000.0)

    st.markdown("#### Travel费用")
    if st.checkbox("Travel费用", value=True, key="v_travel_cb"):
        trips = st.number_input("预计差旅次数（trip）", min_value=0, step=1, value=20, key="v_trips")
        cost_per_trip = st.number_input("平均单次差旅成本", min_value=0.0, step=100.0, value=2000.0, key="v_trip_cost")
        vendor_total_rmb += add_cost_item(rows, "预算模块2：Vendor 花费", "Travel费用", cost_per_trip, trips, "单次成本*次数", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("Recording费用", value=True, key="v_rec_cb"):
        n_rec = st.number_input("Recording 例数", min_value=0, step=1, value=n_planned, key="v_rec_n")
        unit_rec = st.number_input("Recording 单价/例", min_value=0.0, step=50.0, value=200.0, key="v_rec_u")
        vendor_total_rmb += add_cost_item(rows, "预算模块2：Vendor 花费", "Recording费用", unit_rec, n_rec, "例数*单价", input_currency, fx_usd_to_rmb, show_both_currency)

    vendor_total_rmb += add_amount_block("研究者会费用", 150000.0)

    vendor_tax_rate = st.number_input("Vendor税费税率（%）", min_value=0.0, step=1.0, value=6.0, key="v_tax_r")
    vendor_tax_rmb = round1(vendor_total_rmb * vendor_tax_rate / 100.0)
    if vendor_tax_rmb > 0:
        vendor_total_rmb += add_cost_item(
            rows, "预算模块2：Vendor 花费", "Vendor税费",
            from_rmb(vendor_tax_rmb, input_currency, fx_usd_to_rmb), 1,
            f"税率 {vendor_tax_rate:.1f}%",
            input_currency, fx_usd_to_rmb, show_both_currency
        )

# ------------------ 预算模块3：产品物流成本 ------------------ #
product_total_rmb = 0.0
with st.sidebar.expander("预算模块3：产品物流成本", expanded=False):

    if st.checkbox("产品运输费用", value=True, key="p_ship_cb"):
        shipments = st.number_input("运输批次（batch）", min_value=0, step=1, value=10, key="p_ship_n")
        cost = st.number_input("每批运输成本", min_value=0.0, step=100.0, value=3000.0, key="p_ship_u")
        product_total_rmb += add_cost_item(rows, "预算模块3：产品物流成本", "产品运输费用", cost, shipments, "每批*批次", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("仓储费用", value=True, key="p_store_cb"):
        months = st.number_input("仓储月数", min_value=0, step=1, value=24, key="p_store_m")
        cost_m = st.number_input("每月仓储成本", min_value=0.0, step=100.0, value=2000.0, key="p_store_u")
        product_total_rmb += add_cost_item(rows, "预算模块3：产品物流成本", "仓储费用", cost_m, months, "每月*月数", input_currency, fx_usd_to_rmb, show_both_currency)

    if st.checkbox("产品成本", value=True, key="p_cost_cb"):
        unit = st.number_input("产品成本（每例/每套）", min_value=0.0, step=100.0, value=10000.0, key="p_cost_u")
        qty = st.number_input("数量（例/套）", min_value=0, step=1, value=n_planned, key="p_cost_n")
        product_total_rmb += add_cost_item(rows, "预算模块3：产品物流成本", "产品成本", unit, qty, "单价*数量", input_currency, fx_usd_to_rmb, show_both_currency)

# ------------------ 预算模块4：人力资源成本 ------------------ #
resource_total_rmb = 0.0
with st.sidebar.expander("预算模块4：人力资源成本", expanded=False):
    st.caption("费用 = FTE * 每FTE单价（建议每FTE单价填“项目总成本/周期成本”的口径，确保与你的内部核算一致）")
    roles = [
        ("项目经理FTE费用", 0.3, 300000.0),
        ("CRA费用", 0.5, 250000.0),
        ("MCRS费用", 0.2, 180000.0),
        ("Global team费用", 0.1, 500000.0),
    ]
    for role, fte0, unit0 in roles:
        if st.checkbox(role, value=True, key=f"r_{role}_cb"):
            c1, c2 = st.columns(2)
            fte = c1.number_input("FTE", min_value=0.0, step=0.05, value=float(fte0), key=f"r_{role}_fte")
            unit = c2.number_input("每FTE单价", min_value=0.0, step=10000.0, value=float(unit0), key=f"r_{role}_unit")
            resource_total_rmb += add_cost_item(
                rows, "预算模块4：人力资源成本", role,
                unit, fte,
                "FTE * 每FTE单价",
                input_currency, fx_usd_to_rmb, show_both_currency
            )

# ------------------ 预算财年季度分布（用户填写） ------------------ #
st.sidebar.markdown("---")
st.sidebar.subheader("预算财年季度分布（用于Cashflow）")
use_custom_fy_q_pct = st.sidebar.checkbox("启用“自定义财年/季度分配”", value=True)

timeline_default_start = min([x["开始日期"] for x in phase_date_inputs]) if phase_date_inputs else start_date
timeline_default_end = max([x["结束日期"] for x in phase_date_inputs]) if phase_date_inputs else month_add(start_date, project_planned_duration_months - 1)

if "cashflow_editor_df" not in st.session_state:
    st.session_state.cashflow_editor_df = build_default_cashflow_editor_df(timeline_default_start, timeline_default_end)

with st.sidebar.expander("设置财年 + 季度 + 占比（可新增/删除）", expanded=False):
    st.caption("你可以直接修改财年、季度、占比；也可以新增/删除行。系统会按全部行的占比自动归一化分配预算。")

    if st.button("按当前 Timeline 重置 FY/Q 表", key="reset_cashflow_editor"):
        st.session_state.cashflow_editor_df = build_default_cashflow_editor_df(timeline_default_start, timeline_default_end)

    edited_cashflow_df = st.data_editor(
        st.session_state.cashflow_editor_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="cashflow_editor_widget",
        column_config={
            "财年": st.column_config.NumberColumn("财年", min_value=1, step=1, format="%d"),
            "季度": st.column_config.SelectboxColumn("季度", options=[1, 2, 3, 4], required=True),
            "占比(%)": st.column_config.NumberColumn("占比（%）", min_value=0.0, step=1.0, format="%.2f"),
        },
    )

st.session_state.cashflow_editor_df = edited_cashflow_df.copy()

# =====================================================
# 生成按钮
# =====================================================
st.sidebar.markdown("---")
c1, c2 = st.sidebar.columns(2)
generate_btn = c1.button("数据生成")
reset_btn = c2.button("重置生成状态")

if generate_btn:
    st.session_state.generated = True
if reset_btn:
    st.session_state.generated = False

# =====================================================
# 主界面展示
# =====================================================
if not st.session_state.generated:
    st.info("请在左侧完成参数设置，并点击“数据生成”。")
    st.stop()

# Timeline DataFrame（由用户日历输入构建）
timeline_rows = []
for ph in phase_date_inputs:
    timeline_rows.append({
        "阶段": ph["阶段"],
        "子任务": ph["子任务"],
        "类别": ph["类别"],
        "开始日期": pd.to_datetime(ph["开始日期"]),
        "结束日期": pd.to_datetime(ph["结束日期"]),
        "持续时间_月": months_between(ph["开始日期"], ph["结束日期"])
    })

# 插入随访访视（第1次..第N次）
for v in followup_visit_rows:
    timeline_rows.append({
        "阶段": v["阶段"],
        "子任务": v["子任务"],
        "类别": v["类别"],
        "开始日期": pd.to_datetime(v["开始日期"]),
        "结束日期": pd.to_datetime(v["结束日期"]),
        "持续时间_月": months_between(v["开始日期"], v["结束日期"])
    })

df_timeline = pd.DataFrame(timeline_rows)
if not df_timeline.empty:
    df_timeline["阶段排序"] = df_timeline["阶段"].map(LEVEL1_ORDER_INDEX)
    df_timeline["子任务排序"] = df_timeline["子任务"].map(LEVEL2_ORDER_INDEX)
    df_timeline = df_timeline.sort_values(["阶段排序", "子任务排序", "开始日期", "结束日期"]).reset_index(drop=True)
    timeline_start = df_timeline["开始日期"].min().date()
    timeline_end = df_timeline["结束日期"].max().date()
else:
    timeline_start = start_date
    timeline_end = start_date

# 总预算（删除 contingency）
base_total_rmb = round1(site_total_rmb + vendor_total_rmb + product_total_rmb + resource_total_rmb)
total_budget_rmb = base_total_rmb
total_budget_display = round1(from_rmb(total_budget_rmb, input_currency, fx_usd_to_rmb))
smart_quarter_df_rmb, smart_month_alloc_df = build_smart_cashflow(rows, df_timeline, timeline_start, timeline_end)

# ==================== 顶部概览 ==================== #
with st.container():
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"## {project_name} / {study_type}")
        st.caption(
            f"研究类型：{study_type} ｜ 中心数：{int(site_number)} ｜ 计划入组：{int(n_planned)} ｜ 项目计划持续时间（月）：{int(project_planned_duration_months)}"
        )
    with right:
        st.write("")

tab_tl, tab_budget, tab_cash, tab_checks, tab_summary = st.tabs(["Timeline", "Budget", "Cashflow", "Checks", "Summary"])

# =====================================================
# Timeline
# =====================================================
with tab_tl:
    st.subheader("项目时间线预估")

    if df_timeline.empty:
        st.warning("Timeline为空：请在左侧勾选至少一个二级事项并设置日期。")
    else:
        df_level2 = df_timeline.sort_values(["阶段排序", "子任务排序", "开始日期", "结束日期"]).copy()
        df_level1 = (
            df_level2.groupby("阶段", as_index=False)
            .agg({"开始日期": "min", "结束日期": "max"})
        )
        df_level1["阶段排序"] = df_level1["阶段"].map(LEVEL1_ORDER_INDEX)
        df_level1 = df_level1.sort_values(["阶段排序"]).reset_index(drop=True)
        df_level1["持续时间_月"] = df_level1.apply(
            lambda r: months_between(r["开始日期"].date(), r["结束日期"].date()), axis=1
        )

        st.markdown("#### 项目阶段时间预估")
        fig_level1 = px.timeline(
            df_level1,
            x_start="开始日期",
            x_end="结束日期",
            y="阶段",
            color="阶段",
            hover_data=["持续时间_月"],
            category_orders={"阶段": list(reversed(LEVEL1_ORDER))},
        )
        fig_level1.update_yaxes(autorange="reversed", title=None)
        fig_level1.update_layout(
            template="plotly_white",
            height=520,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False,
            font=dict(size=13),
        )
        fig_level1.update_xaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)")
        try:
            today = pd.to_datetime(dt.date.today())
            fig_level1.add_vline(x=today, line_width=2, line_dash="dot", line_color="rgba(37,99,235,0.9)")
            pe_date = month_add(start_date, int(primary_endpoint_time_months))
            fig_level1.add_vline(x=pd.to_datetime(pe_date), line_width=2, line_dash="dash", line_color="rgba(220,38,38,0.85)")
        except Exception:
            pass
        st.plotly_chart(fig_level1, use_container_width=True)

        st.markdown("#### 项目阶段时间预估（详细）")
        level2_display_order = list(reversed([x for lvl in LEVEL1_ORDER for x in TIMELINE_TEMPLATE[lvl] if x in set(df_level2["子任务"]) ]))
        fig_level2 = px.timeline(
            df_level2,
            x_start="开始日期",
            x_end="结束日期",
            y="子任务",
            color="阶段",
            hover_data=["持续时间_月"],
            category_orders={"子任务": level2_display_order},
        )
        fig_level2.update_yaxes(autorange="reversed", title=None)
        fig_level2.update_layout(
            template="plotly_white",
            height=max(620, 28 * len(df_level2)),
            margin=dict(l=10, r=10, t=40, b=10),
            legend_title_text="一级标签",
            font=dict(size=12),
        )
        fig_level2.update_xaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)")
        try:
            today = pd.to_datetime(dt.date.today())
            fig_level2.add_vline(x=today, line_width=2, line_dash="dot", line_color="rgba(37,99,235,0.9)")
            pe_date = month_add(start_date, int(primary_endpoint_time_months))
            fig_level2.add_vline(x=pd.to_datetime(pe_date), line_width=2, line_dash="dash", line_color="rgba(220,38,38,0.85)")
        except Exception:
            pass
        st.plotly_chart(fig_level2, use_container_width=True)

        with st.expander("查看/导出 Timeline 数据（一级标签汇总）", expanded=False):
            show_level1 = df_level1.sort_values(["阶段排序"]).copy()
            st.dataframe(
                show_level1,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "阶段": st.column_config.TextColumn(width="medium"),
                    "开始日期": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                    "结束日期": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                    "持续时间_月": st.column_config.NumberColumn(format="%.1f"),
                },
            )
            csv_level1 = show_level1.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="下载一级标签 Timeline CSV",
                data=csv_level1,
                file_name=f"{project_name}_Timeline_一级标签.csv",
                mime="text/csv",
            )

        with st.expander("查看/导出 Timeline 数据（二级标签明细）", expanded=False):
            display_df = df_level2.copy()
            display_df["阶段"] = display_df["阶段"].mask(display_df["阶段"].eq(display_df["阶段"].shift()), "")
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "阶段": st.column_config.TextColumn(width="medium"),
                    "子任务": st.column_config.TextColumn(width="large"),
                    "类别": st.column_config.TextColumn(width="medium"),
                    "开始日期": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                    "结束日期": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                    "持续时间_月": st.column_config.NumberColumn(format="%.1f"),
                },
            )
            csv_long = df_level2.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="下载二级标签 Timeline CSV",
                data=csv_long,
                file_name=f"{project_name}_Timeline_二级标签.csv",
                mime="text/csv",
            )

# =====================================================
# Budget
# =====================================================
with tab_budget:
    st.subheader("预算明细")

    budget_top_left, budget_top_right = st.columns([3, 2])
    with budget_top_left:
        st.caption("可在此一键切换预算展示币种；底层预算仍统一按 RMB 计算并按当前汇率换算。")
    with budget_top_right:
        budget_display_currency = st.radio(
            "预算显示币种", ["RMB", "USD"], horizontal=True, key="budget_display_currency_radio"
        )

    per_patient_rmb = round1(total_budget_rmb / max(1, int(n_planned)))
    per_site_rmb = round1(total_budget_rmb / max(1, int(site_number)))
    total_budget_display_selected = convert_rmb_to_currency(total_budget_rmb, budget_display_currency, fx_usd_to_rmb)
    per_patient_display_selected = convert_rmb_to_currency(per_patient_rmb, budget_display_currency, fx_usd_to_rmb)
    per_site_display_selected = convert_rmb_to_currency(per_site_rmb, budget_display_currency, fx_usd_to_rmb)

    metric_row1 = st.columns(3)
    metric_row2 = st.columns(3)

    metric_row1[0].metric(
        f"总预算（{budget_display_currency}）",
        fmt_money_full(total_budget_display_selected),
        delta=fmt_metric_delta(total_budget_rmb, "USD" if budget_display_currency == "RMB" else "RMB", fx_usd_to_rmb)
    )
    metric_row1[1].metric("总预算（RMB）", fmt_money_full(total_budget_rmb), delta=fmt_money_cn_rmb(total_budget_rmb))
    metric_row1[2].metric(
        f"每例成本（{budget_display_currency}）",
        fmt_money_full(per_patient_display_selected),
        delta=fmt_metric_delta(per_patient_rmb, "USD" if budget_display_currency == "RMB" else "RMB", fx_usd_to_rmb)
    )

    metric_row2[0].metric(
        f"每中心成本（{budget_display_currency}）",
        fmt_money_full(per_site_display_selected),
        delta=fmt_metric_delta(per_site_rmb, "USD" if budget_display_currency == "RMB" else "RMB", fx_usd_to_rmb)
    )
    metric_row2[1].metric("项目起止（估算）", f"{timeline_start} → {timeline_end}")
    metric_row2[2].metric("项目总月数（估算）", f"{months_between(timeline_start, timeline_end)}")

    df_budget = pd.DataFrame(rows)

    if df_budget.empty:
        st.warning("预算明细为空：请在左侧至少勾选并填写一项费用。")
    else:
        # 小计与合计（以RMB为准）
        module_sums = {
            "预算模块1：研究中心花费": round1(site_total_rmb),
            "预算模块2：Vendor 花费": round1(vendor_total_rmb),
            "预算模块3：产品物流成本": round1(product_total_rmb),
            "预算模块4：人力资源成本": round1(resource_total_rmb),
        }

        def subtotal_row(cat, name, amt_rmb):
            row = {
                "预算模块": cat,
                "费用项目": name,
                f"单价 ({input_currency})": "",
                "数量": "",
                f"小计 ({input_currency})": round1(from_rmb(amt_rmb, input_currency, fx_usd_to_rmb)),
                "备注": "",
            }
            if show_both_currency:
                other = "USD" if str(input_currency).upper() == "RMB" else "RMB"
                row[f"折算单价 ({other})"] = ""
                row[f"折算小计 ({other})"] = round1(from_rmb(amt_rmb, other, fx_usd_to_rmb))
            return row

        display_rows = rows.copy()
        for k, v in module_sums.items():
            display_rows.append(subtotal_row(k, "小计", v))
        display_rows.append(subtotal_row("合计", "总预算", total_budget_rmb))

        df_display = pd.DataFrame(display_rows)

        selected_unit_col = f"单价 ({budget_display_currency})"
        selected_subtotal_col = f"小计 ({budget_display_currency})"
        base_unit_col = f"单价 ({input_currency})"
        base_subtotal_col = f"小计 ({input_currency})"

        if budget_display_currency != input_currency:
            df_display[selected_unit_col] = df_display[base_unit_col].apply(
                lambda x: "" if x == "" else round1(from_rmb(to_rmb(x, input_currency, fx_usd_to_rmb), budget_display_currency, fx_usd_to_rmb))
            )
            df_display[selected_subtotal_col] = df_display[base_subtotal_col].apply(
                lambda x: "" if x == "" else round1(from_rmb(to_rmb(x, input_currency, fx_usd_to_rmb), budget_display_currency, fx_usd_to_rmb))
            )

        display_cols = ["预算模块", "费用项目", selected_unit_col, "数量", selected_subtotal_col, "备注"]
        for c in df_display.columns:
            if c not in display_cols and c.startswith("折算"):
                display_cols.append(c)
        df_display = df_display[display_cols].copy()

        # 为“完整显示数字”准备：把金额列转成字符串（避免表格宽度导致截断/省略）
        money_cols = [c for c in df_display.columns if "单价" in c or "小计" in c]
        for c in money_cols:
            df_display[c] = df_display[c].apply(lambda x: "" if x == "" else fmt_money_full(x))

        display_budget_df = df_display.copy()
        mask_detail = ~display_budget_df["费用项目"].isin(["小计", "总预算"])
        display_budget_df.loc[mask_detail, "预算模块"] = display_budget_df.loc[mask_detail, "预算模块"].mask(
            display_budget_df.loc[mask_detail, "预算模块"].eq(
                display_budget_df.loc[mask_detail, "预算模块"].shift()
            ),
            ""
        )

        st.dataframe(
            display_budget_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "预算模块": st.column_config.TextColumn(width="large"),
                "费用项目": st.column_config.TextColumn(width="medium"),
                selected_unit_col: st.column_config.TextColumn(width="medium"),
                "数量": st.column_config.TextColumn(width="small"),
                selected_subtotal_col: st.column_config.TextColumn(width="medium"),
                "备注": st.column_config.TextColumn(width="large"),
            },
            height=520,
        )

        csv_budget = df_display.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="下载预算明细 CSV",
            data=csv_budget,
            file_name=f"{project_name}_预算明细_{budget_display_currency}.csv",
            mime="text/csv",
        )

# =====================================================
# Cashflow
# =====================================================
with tab_cash:
    st.subheader("预算按财年季度分布")
    st.caption("柱状图已直接基于预算-时间线智能映射后的月度拆分结果生成，并汇总到财年与财年季度。")

    cash_currency = st.radio("Cashflow 显示币种", ["RMB", "USD"], horizontal=True, key="cashflow_display_currency_radio")

    if smart_month_alloc_df.empty:
        st.info("季度分布为空（总预算为0或未形成有效的预算-时间线月度拆分）。")
    else:
        month_cash_df = smart_month_alloc_df.copy()
        month_cash_df["月份"] = pd.to_datetime(month_cash_df["月份"])
        month_cash_df["月份日期"] = month_cash_df["月份"].dt.date
        month_cash_df["财年季度"] = month_cash_df["月份日期"].apply(fiscal_quarter_label)
        month_cash_df["财年"] = month_cash_df["财年季度"].apply(lambda x: parse_fy_quarter_label(x)[0])
        month_cash_df["Q序号"] = month_cash_df["财年季度"].apply(lambda x: parse_fy_quarter_label(x)[1])

        quarter_df_rmb = month_cash_df.groupby(["财年", "Q序号", "财年季度"], as_index=False)["费用_RMB"].sum()
        quarter_df_rmb = quarter_df_rmb.sort_values(["财年", "Q序号"]).reset_index(drop=True)
        quarter_df_rmb["Q"] = quarter_df_rmb["Q序号"].apply(lambda x: f"Q{x}")
        total_cash = max(1e-9, quarter_df_rmb["费用_RMB"].sum())
        quarter_df_rmb["占比(%)"] = quarter_df_rmb["费用_RMB"] / total_cash * 100
        quarter_df_rmb["季度"] = quarter_df_rmb["财年季度"]
        quarter_df_rmb["费用显示"] = quarter_df_rmb["费用_RMB"].apply(lambda x: convert_rmb_to_currency(x, cash_currency, fx_usd_to_rmb))
        y_title = f"费用 ({cash_currency})"

        fy_df = (
            quarter_df_rmb.groupby("财年", as_index=False)["费用显示"]
            .sum()
            .sort_values("财年")
            .reset_index(drop=True)
        )
        fy_df["财年标签"] = fy_df["财年"].apply(lambda x: f"FY{x}")
        fy_df["费用显示"] = fy_df["费用显示"].apply(round1)

        q_df = quarter_df_rmb.copy()
        q_df = q_df.sort_values(["财年", "Q序号"]).reset_index(drop=True)
        q_df["费用显示"] = q_df["费用显示"].apply(round1)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 按财年划分")
            fig_fy = px.bar(
                fy_df,
                x="财年标签",
                y="费用显示",
                text="费用显示"
            )
            fig_fy.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
            fig_fy.update_layout(
                template="plotly_white",
                height=430,
                margin=dict(l=10, r=10, t=40, b=10),
                font=dict(size=13),
                yaxis_title=y_title,
                xaxis_title="财年"
            )
            fig_fy.update_yaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)", tickformat=",")
            st.plotly_chart(fig_fy, use_container_width=True)

        with col2:
            st.markdown("#### 按季度划分")
            fig_q = px.bar(
                q_df,
                x="季度",
                y="费用显示",
                text="费用显示"
            )
            fig_q.update_traces(texttemplate="%{text:,.1f}", textposition="outside")
            fig_q.update_layout(
                template="plotly_white",
                height=430,
                margin=dict(l=10, r=10, t=40, b=10),
                font=dict(size=13),
                yaxis_title=y_title,
                xaxis_title="财年季度"
            )
            fig_q.update_yaxes(showgrid=True, gridcolor="rgba(15,23,42,0.08)", tickformat=",")
            st.plotly_chart(fig_q, use_container_width=True)

        with st.expander("查看预算-时间线智能映射（月度拆分）", expanded=False):
            if smart_month_alloc_df.empty:
                st.info("当前无可展示的智能映射结果。")
            else:
                alloc_display = smart_month_alloc_df.copy()
                alloc_display["月份"] = pd.to_datetime(alloc_display["月份"]).dt.strftime("%Y-%m")
                alloc_display["费用_RMB"] = alloc_display["费用_RMB"].apply(round1)
                alloc_display = alloc_display.sort_values(["月份", "预算模块", "费用项目", "预算阶段"]).reset_index(drop=True)
                st.dataframe(alloc_display, use_container_width=True, hide_index=True)
                csv_alloc = alloc_display.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="下载预算-时间线智能映射 CSV",
                    data=csv_alloc,
                    file_name=f"{project_name}_预算_时间线智能映射.csv",
                    mime="text/csv",
                )

        with st.expander("查看财年/季度明细（可用于对账/导出）", expanded=False):
            quarter_display = quarter_df_rmb[["财年", "Q", "季度", "占比(%)", "费用_RMB"]].copy()

            if str(cash_currency).upper() == "RMB":
                quarter_display["费用 (RMB)"] = quarter_display["费用_RMB"].apply(fmt_money_full)
            else:
                quarter_display[f"费用 ({cash_currency})"] = quarter_df_rmb["费用显示"].apply(fmt_money_full)
                quarter_display["费用 (RMB)"] = quarter_display["费用_RMB"].apply(fmt_money_full)

            quarter_display["占比(%)"] = quarter_display["占比(%)"].apply(lambda x: f"{float(x):.2f}")
            st.dataframe(quarter_display, use_container_width=True, hide_index=True)

            csv_q = quarter_display.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="下载财年季度分布 CSV",
                data=csv_q,
                file_name=f"{project_name}_预算_财年季度分布.csv",
                mime="text/csv",
            )

    st.markdown("---")
    st.subheader("预算模块占比（饼状图）")

    pie_df = pd.DataFrame([
        {"预算模块": "预算模块1：研究中心花费", "金额_RMB": round1(site_total_rmb)},
        {"预算模块": "预算模块2：Vendor 花费", "金额_RMB": round1(vendor_total_rmb)},
        {"预算模块": "预算模块3：产品物流成本", "金额_RMB": round1(product_total_rmb)},
        {"预算模块": "预算模块4：人力资源成本", "金额_RMB": round1(resource_total_rmb)},
    ])
    pie_df = pie_df[pie_df["金额_RMB"] > 0].copy()

    if pie_df.empty:
        st.info("当前各模块金额为0，无法生成饼状图。")
    else:
        pie_df["金额"] = pie_df["金额_RMB"].apply(lambda x: round1(from_rmb(x, input_currency, fx_usd_to_rmb)))
        fig_pie = px.pie(
            pie_df,
            values="金额",
            names="预算模块",
            hover_data=["金额_RMB"],
            color_discrete_sequence=get_color_sequence(pie_color_theme, len(pie_df)),
        )
        fig_pie.update_traces(textinfo="percent+label")
        fig_pie.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=10, r=10, t=40, b=10),
            font=dict(size=13),
            legend_title_text="预算模块",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        with st.expander("查看模块金额（RMB）", expanded=False):
            pie_display = pie_df[["预算模块", "金额_RMB"]].copy()
            pie_display["金额_RMB"] = pie_display["金额_RMB"].apply(fmt_money_full)
            st.dataframe(pie_display, use_container_width=True, hide_index=True)

        st.markdown("### 各预算模块内部花费占比")
        detail_df = pd.DataFrame(rows).copy()

        if not detail_df.empty:
            amount_col = f"小计 ({input_currency})"
            detail_df[amount_col] = pd.to_numeric(detail_df[amount_col], errors="coerce").fillna(0)
            detail_df["金额_RMB"] = detail_df[amount_col].apply(
                lambda x: round1(to_rmb(x, input_currency, fx_usd_to_rmb))
            )

            module_order = [
                "预算模块1：研究中心花费",
                "预算模块2：Vendor 花费",
                "预算模块3：产品物流成本",
                "预算模块4：人力资源成本",
            ]

            module_title_map = {
                "预算模块1：研究中心花费": "模块1：研究中心花费占比",
                "预算模块2：Vendor 花费": "模块2：Vendor 花费占比",
                "预算模块3：产品物流成本": "模块3：产品物流成本占比",
                "预算模块4：人力资源成本": "模块4：人力资源成本占比",
            }

            for i in range(0, len(module_order), 2):
                cols = st.columns(2)
                for j, module_name in enumerate(module_order[i:i+2]):
                    module_df = (
                        detail_df[detail_df["预算模块"] == module_name]
                        .groupby("费用项目", as_index=False)["金额_RMB"]
                        .sum()
                    )
                    module_df = module_df[module_df["金额_RMB"] > 0].copy()

                    with cols[j]:
                        if module_df.empty:
                            st.info(f"{module_name} 当前无可展示费用。")
                        else:
                            module_df["金额"] = module_df["金额_RMB"].apply(
                                lambda x: round1(from_rmb(x, input_currency, fx_usd_to_rmb))
                            )
                            fig_module = px.pie(
                                module_df,
                                values="金额",
                                names="费用项目",
                                hover_data=["金额_RMB"],
                                color_discrete_sequence=get_color_sequence(pie_color_theme, len(module_df)),
                            )
                            fig_module.update_traces(textinfo="percent")
                            fig_module.update_layout(
                                template="plotly_white",
                                height=420,
                                margin=dict(l=10, r=10, t=50, b=10),
                                font=dict(size=12),
                                title=module_title_map.get(module_name, module_name),
                                legend_title_text="费用项目",
                            )
                            st.plotly_chart(fig_module, use_container_width=True)

                            with st.expander(f"查看 {module_name} 明细（RMB）", expanded=False):
                                module_display = module_df[["费用项目", "金额_RMB"]].copy()
                                module_display["金额_RMB"] = module_display["金额_RMB"].apply(fmt_money_full)
                                st.dataframe(module_display, use_container_width=True, hide_index=True)

# =====================================================
# Checks
# =====================================================
with tab_checks:
    st.subheader("一致性检查与提示（辅助项目管理）")

    checks = []
    tl_months = months_between(timeline_start, timeline_end)
    if abs(tl_months - int(project_planned_duration_months)) >= 6:
        checks.append(f"项目预计持续时间（{int(project_planned_duration_months)}月）与当前时间线跨度（{tl_months}月）差异较大：建议复核各阶段起止日期或持续时间口径。")

    enroll_phase = next((x for x in phase_date_inputs if x["子任务"] == "受试者入组"), None)
    if enroll_phase is not None:
        enroll_user_m = months_between(enroll_phase["开始日期"], enroll_phase["结束日期"])
        if abs(enroll_user_m - enroll_months_est) >= 3:
            checks.append(f"“受试者入组”按速率粗略估算约 {enroll_months_est} 月，但你当前设置为 {enroll_user_m} 月，建议复核中心启动节奏与入组效率。")

    if use_custom_fy_q_pct:
        tmp_cf = st.session_state.get("cashflow_editor_df", pd.DataFrame())
        if tmp_cf is None or tmp_cf.empty:
            checks.append("未设置财年季度分配表：Cashflow 将无法按自定义 FY/Q 分配。")
        else:
            pct_sum = pd.to_numeric(tmp_cf.get("占比(%)", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
            if pct_sum <= 0:
                checks.append("财年季度分配表的占比合计为0：Cashflow 将无法按有效比例分配。")

    if checks:
        for c in checks:
            st.warning(c)
    else:
        st.success("未发现明显风险信号（仍建议结合项目经验进行复核）。")

# =====================================================
# Summary
# =====================================================
with tab_summary:
    st.subheader("项目摘要")

    if study_type == "上市前临床研究":
        study_design_text = "Single arm, Pre-market, Prospective"
    elif study_type == "上市后临床研究":
        study_design_text = "Post-market, Prospective"
    elif study_type == "ERP":
        study_design_text = "ERP"
    elif study_type == "回顾性分析":
        study_design_text = "Retrospective"
    else:
        study_design_text = str(study_type)

    estimated_cost_without_product_rmb = round1(total_budget_rmb - product_total_rmb)
    estimated_cost_without_product_display = round1(from_rmb(estimated_cost_without_product_rmb, "USD", fx_usd_to_rmb))
    estimated_cost_total_display = round1(from_rmb(total_budget_rmb, "USD", fx_usd_to_rmb))
    estimated_product_cost_display = round1(from_rmb(product_total_rmb, "USD", fx_usd_to_rmb))
    estimated_per_subject_without_product_display = round1(estimated_cost_without_product_display / max(1, int(n_planned)))

    study_start_year = timeline_start.year if timeline_start else start_date.year
    study_end_year = timeline_end.year if timeline_end else start_date.year

    # Summary-compatible follow-up variables
    if "followup_months" not in locals():
        followup_months = int(project_planned_duration_months)
    if "followup_visits_n" not in locals():
        followup_visits_n = 0
        if "use_visit_breakdown" in locals() and use_visit_breakdown and "visits_df" in locals() and visits_df is not None:
            try:
                followup_visits_n = int(sum(1 for _, r in visits_df.iterrows() if str(r.get("访视名称", "")).strip()))
            except Exception:
                followup_visits_n = 0

    summary_rows = [
        {"项目": "Study Title", "内容": project_name},
        {"项目": "Study Design", "内容": study_design_text},
        {"项目": "Target FU Duration", "内容": format_fu_years_text(followup_months)},
        {"项目": "Primary Endpoint", "内容": format_endpoint_text(primary_endpoint_time_months)},
        {"项目": "FU visits (30d,6M,1Y-3Y)", "内容": int(followup_visits_n)},
        {"项目": "Estimated Enrolments", "内容": int(n_planned)},
        {"项目": "Estimated # of Sites", "内容": int(site_number)},
        {"项目": "Estimated Study Start Date", "内容": study_start_year},
        {"项目": "Estimated Study End Date", "内容": study_end_year},
        {"项目": "Estimated Cost without Product Cost (USD Dollars)", "内容": f"${fmt_money_full(estimated_cost_without_product_display)}"},
        {"项目": "Estimated Cost In Total(USD Dollars)", "内容": f"${fmt_money_full(estimated_cost_total_display)}"},
        {"项目": "Estimated Product Cost (USD Dollars)", "内容": f"${fmt_money_full(estimated_product_cost_display)}"},
        {"项目": "Estimated Per Subject Cost without product(USD Dollars)", "内容": f"${fmt_money_full(estimated_per_subject_without_product_display)}"},
    ]

    df_summary = pd.DataFrame(summary_rows)

    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:2rem;
            font-weight:700;
            margin-top:0.5rem;
            margin-bottom:1rem;
        ">
            {project_name}
        </div>
        """,
        unsafe_allow_html=True
    )

    table_rows_html = ""
    for i, row in df_summary.iterrows():
        label = row["项目"]
        value = row["内容"]
        if i == 9:
            value_html = f"<span style='color:#d60000; font-weight:700;'>{value}</span>"
        else:
            value_html = str(value)
        table_rows_html += f"""
        <tr>
            <td style='border:1px solid #222; padding:10px; width:48%; font-weight:700; vertical-align:top; word-break:break-word;'>{label}</td>
            <td style='border:1px solid #222; padding:10px; width:52%; vertical-align:top; word-break:break-word;'>{value_html}</td>
        </tr>
        """

    summary_html = f"""
    <div style='width:100%; background:#FFFFFF;'>
        <table style='width:100%; border-collapse:collapse; font-size:18px; table-layout:fixed;'>
            {table_rows_html}
        </table>
    </div>
    """
    summary_height = max(520, 84 + len(df_summary) * 58)
    components.html(summary_html, height=summary_height, scrolling=False)

    csv_summary = df_summary.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="下载 Summary CSV",
        data=csv_summary,
        file_name=f"{project_name}_Summary.csv",
        mime="text/csv",
    )
