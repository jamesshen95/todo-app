#!/usr/bin/env python3
"""
財務比率報表產生器 - 台股（MOPS）+ 國際股票（Yahoo Finance）

安裝套件: pip install flask requests beautifulsoup4 yfinance
執行程式: python app.py
開啟瀏覽器: http://localhost:5000
"""

from flask import Flask, request, Response
import requests as req
from bs4 import BeautifulSoup
import re, json, html

app = Flask(__name__)

# ─────────────────────────────────────────────
#  MOPS 工具函式
# ─────────────────────────────────────────────

BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': '*/*',
    'Accept-Language': 'zh-TW,zh;q=0.9',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://mops.twse.com.tw',
    'Referer': 'https://mops.twse.com.tw/mops/web/index',
}

def ce_to_roc(y): return y - 1911

def to_float(s):
    s = str(s).strip().replace(',', '').replace(' ', '')
    if not s or s in ['--', '－', 'N/A', 'n/a', '']:
        return None
    neg = s.startswith('(') or s.startswith('-')
    s = re.sub(r'[^\d.]', '', s)
    try:
        v = float(s)
        return -v if neg else v
    except:
        return None

def post_mops(session, endpoint, stock_id, roc_year):
    url = f'https://mops.twse.com.tw/mops/web/{endpoint}'
    body = (
        f'encodeURIComponent_result=1&run=web'
        f'&co_id={stock_id}&year={roc_year}&season=04'
    )
    r = session.post(url, data=body, headers=BROWSER_HEADERS, timeout=20)
    r.encoding = 'utf-8'
    return r.text

def parse_table_rows(html_text):
    """Return list of (label, [values...]) from all tables in html_text."""
    soup = BeautifulSoup(html_text, 'html.parser')
    rows = []
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            cells = [td.get_text(' ', strip=True) for td in tr.find_all(['td', 'th'])]
            if len(cells) >= 2:
                rows.append((cells[0], cells[1:]))
    return rows

def find_val(rows, *keywords):
    """Find first numeric value in rows whose label matches any keyword."""
    for label, vals in rows:
        label_norm = label.replace(' ', '')
        for kw in keywords:
            if kw in label_norm:
                for v in vals:
                    f = to_float(v)
                    if f is not None:
                        return f
    return None

# ─────────────────────────────────────────────
#  Data Fetchers (per year)
# ─────────────────────────────────────────────

def fetch_ratios(session, stock_id, ce_year):
    """t05st22 → pre-calculated annual financial ratios"""
    rows = parse_table_rows(post_mops(session, 'ajax_t05st22', stock_id, ce_to_roc(ce_year)))
    return {
        'debt_ratio':      find_val(rows, '負債占資產比率', '資產負債率'),
        'lt_cap_ratio':    find_val(rows, '長期資金占不動產', '長期資產適合率'),
        'current_ratio':   find_val(rows, '流動比率'),
        'quick_ratio':     find_val(rows, '速動比率'),
        'ar_turnover':     find_val(rows, '應收款項周轉率'),
        'avg_coll_days':   find_val(rows, '平均收現日數'),
        'inv_turnover':    find_val(rows, '存貨周轉率'),
        'avg_inv_days':    find_val(rows, '平均銷貨日數', '平均在庫'),
        'ppe_turnover':    find_val(rows, '不動產廠房及設備周轉率', '固定資產周轉率'),
        'ta_turnover':     find_val(rows, '總資產周轉率'),
        'roa':             find_val(rows, '資產報酬率'),
        'roe':             find_val(rows, '權益報酬率'),
        'pretax_capital':  find_val(rows, '稅前純益占實收資本'),
        'gross_margin':    find_val(rows, '營業毛利率'),
        'op_margin':       find_val(rows, '營業利益率'),
        'net_margin':      find_val(rows, '純益率', '淨利率'),
        'eps':             find_val(rows, '每股盈餘'),
        'cf_ratio':        find_val(rows, '現金流量比率'),
        'cf_adequacy':     find_val(rows, '現金流量允當比率'),
        'cf_reinvest':     find_val(rows, '現金再投資比率'),
    }

def fetch_balance_sheet(session, stock_id, ce_year):
    """t163sb05 → balance sheet items"""
    rows = parse_table_rows(post_mops(session, 'ajax_t163sb05', stock_id, ce_to_roc(ce_year)))
    return {
        'cash':         find_val(rows, '現金及約當現金', '現金與約當現金', '貨幣資金'),
        'ar':           find_val(rows, '應收帳款淨額', '應收帳款及票據', '應收帳款'),
        'inventory':    find_val(rows, '存貨'),
        'current_assets': find_val(rows, '流動資產合計', '流動資產總額', '流動資產'),
        'ppe':          find_val(rows, '不動產廠房及設備', '固定資產淨額', '不動產、廠房及設備'),
        'total_assets': find_val(rows, '資產總計', '資產總額', '資產合計'),
        'ap':           find_val(rows, '應付帳款'),
        'current_liab': find_val(rows, '流動負債合計', '流動負債總額', '流動負債'),
        'lt_liab':      find_val(rows, '非流動負債合計', '長期負債合計', '非流動負債', '長期負債'),
        'paid_in_cap':  find_val(rows, '股本', '實收資本'),
        'equity':       find_val(rows, '權益總計', '股東權益合計', '權益合計', '股東權益'),
    }

def fetch_cashflow(session, stock_id, ce_year):
    """t163sb06 → cash flow statement"""
    rows = parse_table_rows(post_mops(session, 'ajax_t163sb06', stock_id, ce_to_roc(ce_year)))
    return {
        'operating':  find_val(rows, '營業活動之淨現金', '來自營業活動', '營業活動'),
        'investing':  find_val(rows, '投資活動之淨現金', '來自投資活動', '投資活動'),
        'financing':  find_val(rows, '籌資活動之淨現金', '來自籌資活動', '籌資活動'),
    }

def fetch_company_name(session, stock_id):
    """Fetch company name from MOPS"""
    try:
        r = session.get(
            f'https://mops.twse.com.tw/mops/web/ajax_t05st22?'
            f'encodeURIComponent_result=1&run=web&co_id={stock_id}&year=113&season=04',
            headers=BROWSER_HEADERS, timeout=10
        )
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        # Company name often in title or first table header
        title = soup.find('title')
        if title:
            m = re.search(r'[一-鿿]{2,}', title.get_text())
            if m:
                return m.group()
        # Try caption
        cap = soup.find('caption')
        if cap:
            return cap.get_text(strip=True)
    except:
        pass
    return ''

# ─────────────────────────────────────────────
#  Report HTML Builder
# ─────────────────────────────────────────────

def fmt(v, dec=1):
    if v is None or (isinstance(v, float) and (v != v)):
        return 'N/A'
    return f'{v:.{dec}f}'

def fmt_cf(v):
    if v is None:
        return '—'
    abs_v = abs(v)
    s = f'{abs_v:,.0f}'
    return f'({s})' if v < 0 else s

def pct_of(part, total):
    if total and total != 0 and part is not None:
        return part / total * 100
    return None

def build_report(company_num, company_name, years, ratios_list, bs_list, cf_list, currency='百萬元'):
    def r(vals, dec=1):
        return ''.join(
            f'<td class="na">N/A</td>' if v is None else f'<td>{fmt(v, dec)}</td>'
            for v in vals
        )

    def bs_pct(field):
        cells = []
        for bs in bs_list:
            ta = bs.get('total_assets')
            v = bs.get(field)
            pv = pct_of(v, ta)
            cells.append(f'<td class="na">N/A</td>' if pv is None else f'<td>{fmt(pv)}</td>')
        return ''.join(cells)

    def bs_pct_bold(field):
        cells = []
        for bs in bs_list:
            ta = bs.get('total_assets')
            v = bs.get(field)
            pv = pct_of(v, ta)
            cells.append(
                f'<td class="bold-row na">N/A</td>' if pv is None
                else f'<td class="bold-row">{fmt(pv)}</td>'
            )
        return ''.join(cells)

    yr_ths = ''.join(f'<th class="yr-col">{y}</th>' for y in years)
    yr_100 = ''.join(
        f'<td class="bold-row na">N/A</td>' if bs.get('total_assets') is None
        else f'<td class="bold-row">100</td>'
        for bs in bs_list
    )

    has_ratios = any(any(v is not None for v in ro.values()) for ro in ratios_list)

    is_intl = not bool(re.match(r'^\d{4,6}$', str(company_num)))
    notice = ''
    if not has_ratios:
        if is_intl:
            notice = '''<div class="notice">
          ⚠️ 無法從 Yahoo Finance 取得資料，可能原因：
          <ul>
            <li>股票代號輸入錯誤（美股請用英文代號，例如 GOOGL、AAPL）</li>
            <li>Yahoo Finance 暫時無法連線</li>
            <li>該年度財報尚未公告</li>
          </ul>
        </div>'''
        else:
            notice = '''<div class="notice">
          ⚠️ 無法從 MOPS 取得資料，可能原因：
          <ul>
            <li>股票代號輸入錯誤（請確認為上市公司）</li>
            <li>MOPS 網站暫時維護</li>
            <li>該公司尚未公告年度財報</li>
          </ul>
          請到 <a href="https://mops.twse.com.tw" target="_blank">mops.twse.com.tw</a> 確認股票代號。
        </div>'''

    return f'''
<div class="report-card">
  {notice}
  <div class="report-header">
    <div class="rh-num">{html.escape(company_num)}</div>
    <div class="rh-logo">
      <div class="rh-logo-sm">Winning</div>
      <div class="rh-logo-lg">The<br>GAMES</div>
    </div>
    <div class="rh-name">{html.escape(company_name)}</div>
    <div class="rh-ifrs">IFRS applied</div>
    <div class="rh-spacer"></div>
    <div class="rh-links">
      http://mops.twse.com.tw/mops/web/t05st22_q1#<br>
      https://tw.stock.yahoo.com/d/s/company_0000.html
    </div>
  </div>
  <div class="report-body">
    <div class="left-panel">
      <table>
        <thead><tr>
          <th class="lbl-th">會計項目 (占總資產%)</th>
          {''.join(f'<th class="yr-col">{y}</th>' for y in years)}
        </tr></thead>
        <tbody>
          <tr><td class="row-lbl">現金與約當現金 = 貨幣資金</td>{bs_pct('cash')}</tr>
          <tr><td class="row-lbl">應收帳款</td>{bs_pct('ar')}</tr>
          <tr><td class="row-lbl">存貨</td>{bs_pct('inventory')}</tr>
          <tr><td class="row-lbl bold-row">流動資產</td>{bs_pct_bold('current_assets')}</tr>
          <tr><td class="row-lbl bold-row">總資產</td>{yr_100}</tr>
          <tr><td class="row-lbl">應付帳款</td>{bs_pct('ap')}</tr>
          <tr><td class="row-lbl bold-row">流動負債</td>{bs_pct_bold('current_liab')}</tr>
          <tr><td class="row-lbl">長期負債</td>{bs_pct('lt_liab')}</tr>
          <tr><td class="row-lbl bold-row">股東權益</td>{bs_pct_bold('equity')}</tr>
          <tr><td class="row-lbl bold-row">總負債+股東權益</td>{yr_100}</tr>
        </tbody>
      </table>
    </div>
    <div class="right-panel">
      <table>
        <thead><tr>
          <th class="cat-th">類別</th>
          <th class="lbl-th">財務比率</th>
          {yr_ths}
        </tr></thead>
        <tbody>
          <tr>
            <td class="category" rowspan="2">財務<br>結構</td>
            <td class="ratio-lbl">負債占資產比率(%) = 資產負債率</td>
            {r([ro.get('debt_ratio') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">長期資金占不動產/廠房及設備比率(%)<br>= 長期資產適合率</td>
            {r([ro.get('lt_cap_ratio') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="category" rowspan="2">償債<br>能力</td>
            <td class="ratio-lbl">流動比率(%)</td>
            {r([ro.get('current_ratio') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">速動比率(%)</td>
            {r([ro.get('quick_ratio') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="category" rowspan="6">經營<br>能力</td>
            <td class="ratio-lbl">應收款項周轉率(次)</td>
            {r([ro.get('ar_turnover') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">平均收現日數</td>
            {r([ro.get('avg_coll_days') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">存貨周轉率(次)</td>
            {r([ro.get('inv_turnover') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">平均銷貨日數（平均在庫天數）</td>
            {r([ro.get('avg_inv_days') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">不動產/廠房及設備周轉率(次)<br>= 固定資產周轉率</td>
            {r([ro.get('ppe_turnover') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">總資產周轉率(次)</td>
            {r([ro.get('ta_turnover') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="category" rowspan="7">獲利<br>能力</td>
            <td class="ratio-lbl">資產報酬率(%)　RoA = 總資產收益率</td>
            {r([ro.get('roa') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">權益報酬率(%)　RoE = 淨資產收益率</td>
            {r([ro.get('roe') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">稅前純益占實收資本比率(%)</td>
            {r([ro.get('pretax_capital') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">營業毛利率(%)</td>
            {r([ro.get('gross_margin') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">營業利益率(%)</td>
            {r([ro.get('op_margin') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">純益率(%) = 淨利率</td>
            {r([ro.get('net_margin') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">每股盈餘(元) = 每股收益</td>
            {r([ro.get('eps') for ro in ratios_list], 2)}
          </tr>
          <tr>
            <td class="category" rowspan="3">現金<br>流量</td>
            <td class="ratio-lbl">現金流量比率(%)</td>
            {r([ro.get('cf_ratio') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">現金流量允當比率(%)</td>
            {r([ro.get('cf_adequacy') for ro in ratios_list])}
          </tr>
          <tr>
            <td class="ratio-lbl">現金再投資比率(%)</td>
            {r([ro.get('cf_reinvest') for ro in ratios_list])}
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div class="cf-section">
    <table>
      <thead><tr>
        <th class="lbl-th">單位:{currency}</th>
        {''.join(f'<th class="yr-col">{y}</th>' for y in years)}
      </tr></thead>
      <tbody>
        <tr>
          <td class="row-lbl">營業活動現金流量（from 損益表）</td>
          {''.join(f'<td>{fmt_cf(cf.get("operating"))}</td>' for cf in cf_list)}
        </tr>
        <tr>
          <td class="row-lbl">投資活動現金流量（from 資產負債表左邊）</td>
          {''.join(f'<td>{fmt_cf(cf.get("investing"))}</td>' for cf in cf_list)}
        </tr>
        <tr>
          <td class="row-lbl">籌資活動現金流量（from 資產負債表右邊）</td>
          {''.join(f'<td>{fmt_cf(cf.get("financing"))}</td>' for cf in cf_list)}
        </tr>
      </tbody>
    </table>
  </div>
</div>'''

# ─────────────────────────────────────────────
#  HTML Pages
# ─────────────────────────────────────────────

STYLE = '''
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Noto Sans TC', Arial, sans-serif; background: #f0f0f0; font-size: 13px; color: #222; }

/* ── Index ── */
.index-wrap { max-width: 560px; margin: 60px auto; background: #fff; border-radius: 12px; padding: 36px 32px; box-shadow: 0 4px 20px rgba(0,0,0,.12); }
.index-wrap h1 { font-size: 22px; margin-bottom: 6px; }
.index-wrap p { color: #666; font-size: 13px; margin-bottom: 28px; line-height: 1.6; }
.form-row { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; }
.form-row label { display: flex; flex-direction: column; gap: 5px; font-size: 13px; font-weight: bold; flex: 1; min-width: 130px; }
.form-row input { border: 1.5px solid #ccc; border-radius: 6px; padding: 10px 12px; font-size: 16px; width: 100%; }
.form-row input:focus { outline: none; border-color: #1a5c2a; }
.btn-query { display: block; width: 100%; padding: 14px; background: #1a5c2a; color: #fff; border: none; border-radius: 8px; font-size: 17px; font-weight: bold; cursor: pointer; margin-top: 4px; }
.hint { font-size: 11px; color: #888; margin-top: 12px; line-height: 1.7; }
.hint a { color: #1a5c2a; }

/* ── Loading ── */
.loading { text-align: center; padding: 80px 20px; font-size: 18px; color: #555; }

/* ── Report page ── */
.report-page { max-width: 1100px; margin: 16px auto; padding: 0 8px; }
.rp-actions { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.btn-back  { padding: 10px 18px; background: #555; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-print { padding: 10px 18px; background: #1a5c2a; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.scroll-hint { font-size: 11px; color: #888; margin-bottom: 6px; display: none; }
@media(max-width:700px) { .scroll-hint { display: block; } }
.report-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }

/* ── Report card ── */
.notice { background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px; font-size: 13px; }
.notice ul { margin: 6px 0 0 20px; }
.notice a { color: #856404; }
.report-card { background: #fff; border: 2px solid #333; margin-bottom: 24px; }
.report-header { display: flex; align-items: stretch; background: #222; color: #fff; }
.rh-num  { font-size: 48px; font-weight: 900; padding: 10px 16px; display: flex; align-items: center; line-height: 1; }
.rh-logo { border-left: 2px solid #555; border-right: 2px solid #555; padding: 8px 14px; display: flex; flex-direction: column; justify-content: center; }
.rh-logo-sm { font-size: 10px; color: #ccc; letter-spacing: 1px; text-transform: uppercase; }
.rh-logo-lg { font-size: 17px; font-weight: 900; line-height: 1.2; }
.rh-name   { padding: 8px 14px; font-size: 18px; font-weight: bold; display: flex; align-items: center; }
.rh-ifrs   { padding: 8px; font-size: 10px; color: #aaa; display: flex; align-items: center; }
.rh-spacer { flex: 1; }
.rh-links  { padding: 8px 12px; font-size: 9px; color: #aaa; display: flex; flex-direction: column; justify-content: center; }

.report-body { display: flex; }

/* Left panel */
.left-panel { width: 210px; flex-shrink: 0; border-right: 1px solid #ccc; }
.left-panel table { width: 100%; border-collapse: collapse; }
.lbl-th { background: #555 !important; color: #fff !important; padding: 5px 7px !important; text-align: left !important; font-size: 11px !important; }
.yr-col { background: #555; color: #fff; padding: 5px 7px; text-align: center; font-size: 11px; width: 48px; }
.left-panel td { padding: 3px 6px; font-size: 11px; border-bottom: 1px solid #ddd; text-align: right; }
.row-lbl { text-align: left !important; background: #f5f5f5; white-space: nowrap; font-size: 10.5px; }
.bold-row { font-weight: bold; background: #e8e8e8 !important; }
.na { color: #aaa; text-align: center !important; }

/* Right panel */
.right-panel { flex: 1; }
.right-panel table { width: 100%; border-collapse: collapse; }
.cat-th { background: #555; color: #fff; padding: 5px 7px; font-size: 11px; width: 44px; }
.right-panel .yr-col { width: 54px; }
.right-panel td { padding: 3px 8px; font-size: 11px; border-bottom: 1px solid #ddd; text-align: right; white-space: nowrap; }
.category { background: #333 !important; color: #fff !important; font-weight: bold; font-size: 12px; text-align: center !important; vertical-align: middle; width: 44px; }
.ratio-lbl { text-align: left !important; background: #f5f5f5; padding-left: 8px !important; font-size: 11px; }
.right-panel .na { text-align: center !important; }

/* Cash flow */
.cf-section { border-top: 2px solid #333; }
.cf-section table { width: 100%; border-collapse: collapse; }
.cf-section th { background: #555; color: #fff; padding: 5px 8px; font-size: 11px; text-align: center; }
.cf-section td { padding: 3px 8px; font-size: 11px; border-bottom: 1px solid #ddd; text-align: right; }

@media print {
  body { background: #fff; }
  .rp-actions, .scroll-hint { display: none !important; }
  .report-card { page-break-after: always; }
}
</style>'''

INDEX_HTML = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>財務比率報表產生器</title>
{STYLE}
</head>
<body>
<div class="index-wrap">
  <h1>財務比率報表產生器</h1>
  <p>輸入台股代號，自動從公開資訊觀測站（MOPS）抓取三年財報，<br>產生 Winning The Games 格式分析表。</p>
  <form method="POST" action="/report">
    <div class="form-row">
      <label>股票代號（必填）
        <input type="text" name="stock_id" placeholder="例：2330" required maxlength="8" autocomplete="off">
      </label>
      <label>公司名稱（選填）
        <input type="text" name="company_name" placeholder="例：台積電（留空自動查詢）">
      </label>
    </div>
    <div class="form-row">
      <label>年度1 <input type="text" name="y1" value="2023" maxlength="4"></label>
      <label>年度2 <input type="text" name="y2" value="2024" maxlength="4"></label>
      <label>年度3 <input type="text" name="y3" value="2025" maxlength="4"></label>
    </div>
    <button class="btn-query" type="submit">自動抓取並生成報表 →</button>
  </form>
  <p class="hint">
    資料來源：<a href="https://mops.twse.com.tw" target="_blank">公開資訊觀測站 (MOPS)</a>，僅支援台灣上市公司。<br>
    抓取需要 10–30 秒，請耐心等待。
  </p>
</div>
</body>
</html>'''


def report_page(company_num, company_name, years, ratios_list, bs_list, cf_list, currency='百萬元'):
    card = build_report(company_num, company_name, years, ratios_list, bs_list, cf_list, currency)
    return f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(company_name or company_num)} 財務比率報表</title>
{STYLE}
</head>
<body>
<div class="report-page">
  <div class="rp-actions">
    <button class="btn-back" onclick="history.back()">← 返回</button>
    <button class="btn-print" onclick="window.print()">列印 / 儲存PDF</button>
  </div>
  <p class="scroll-hint">← 左右滑動查看完整報表 →</p>
  <div class="report-scroll">{card}</div>
</div>
</body>
</html>'''

# ─────────────────────────────────────────────
#  International Stocks (yfinance / Yahoo Finance)
# ─────────────────────────────────────────────

def is_taiwan_stock(stock_id):
    """4–6 digit codes are Taiwan listed/OTC stocks."""
    return bool(re.match(r'^\d{4,6}$', stock_id))

def _yf_get(df, year, *keys):
    """Return value in millions for the first matching key/year in a yfinance DataFrame."""
    if df is None or df.empty:
        return None
    for col in df.columns:
        col_year = col.year if hasattr(col, 'year') else int(str(col)[:4])
        if col_year == year:
            for k in keys:
                if k in df.index:
                    try:
                        v = float(df.loc[k, col])
                        if v == v:           # not NaN
                            return v / 1_000_000
                    except:
                        pass
    return None

def _yf_get_eps(df, year):
    """EPS is already per-share, no unit conversion."""
    if df is None or df.empty:
        return None
    for col in df.columns:
        col_year = col.year if hasattr(col, 'year') else int(str(col)[:4])
        if col_year == year:
            for k in ('Diluted EPS', 'Basic EPS', 'EPS'):
                if k in df.index:
                    try:
                        v = float(df.loc[k, col])
                        if v == v:
                            return v
                    except:
                        pass
    return None

def _safe_pct(num, den):
    return num / den * 100 if (num is not None and den and den != 0) else None

def _safe_div(num, den):
    return num / den if (num is not None and den and den != 0) else None

def _avg(a, b):
    if a is not None and b is not None:
        return (a + b) / 2
    return a if a is not None else b

def fetch_international_data(ticker_symbol, ce_years):
    import yfinance as yf
    t = yf.Ticker(ticker_symbol.upper())

    # Support both old (.financials) and new (.income_stmt) yfinance APIs
    inc = getattr(t, 'income_stmt', None) or getattr(t, 'financials', None)
    bal = getattr(t, 'balance_sheet', None)
    cfs = getattr(t, 'cashflow', None)
    info = t.info or {}

    company_name = info.get('longName') or info.get('shortName') or ticker_symbol.upper()
    currency = info.get('currency', 'USD')

    ratios_list, bs_list, cf_list = [], [], []

    for i, yr in enumerate(ce_years):
        # ── Balance Sheet ──
        ta   = _yf_get(bal, yr, 'Total Assets')
        ca   = _yf_get(bal, yr, 'Current Assets')
        cash = _yf_get(bal, yr, 'Cash And Cash Equivalents',
                       'Cash Cash Equivalents And Short Term Investments',
                       'Cash Financial')
        ar   = _yf_get(bal, yr, 'Accounts Receivable', 'Net Receivables',
                       'Receivables')
        inv  = _yf_get(bal, yr, 'Inventory')
        cl   = _yf_get(bal, yr, 'Current Liabilities',
                       'Total Current Liabilities Net Minority Interest')
        eq   = _yf_get(bal, yr, 'Stockholders Equity', 'Common Stock Equity',
                       'Total Equity Gross Minority Interest')
        ll   = _yf_get(bal, yr, 'Long Term Debt',
                       'Total Non Current Liabilities Net Minority Interest',
                       'Non Current Deferred Revenue Non Current')
        ppe  = _yf_get(bal, yr, 'Net PPE', 'Property Plant Equipment Net')
        ap   = _yf_get(bal, yr, 'Accounts Payable', 'Payables')

        bs_list.append({'cash': cash, 'ar': ar, 'inventory': inv,
                        'current_assets': ca, 'ppe': ppe, 'total_assets': ta,
                        'ap': ap, 'current_liab': cl, 'lt_liab': ll, 'equity': eq})

        # ── Income Statement ──
        rev  = _yf_get(inc, yr, 'Total Revenue')
        cogs = _yf_get(inc, yr, 'Cost Of Revenue')
        gp   = _yf_get(inc, yr, 'Gross Profit')
        oi   = _yf_get(inc, yr, 'Operating Income', 'Ebit')
        ie   = _yf_get(inc, yr, 'Interest Expense')
        pti  = _yf_get(inc, yr, 'Pretax Income')
        ni   = _yf_get(inc, yr, 'Net Income')
        eps  = _yf_get_eps(inc, yr)

        cf_list.append({
            'operating': _yf_get(cfs, yr, 'Operating Cash Flow',
                                  'Cash Flows From Operations'),
            'investing':  _yf_get(cfs, yr, 'Investing Cash Flow',
                                  'Cash Flows From Investing'),
            'financing':  _yf_get(cfs, yr, 'Financing Cash Flow',
                                  'Cash Flows From Financing'),
        })

        # ── Calculate ratios using previous year averages ──
        prev = bs_list[i - 1] if i > 0 else {}
        avg_ta  = _avg(ta,  prev.get('total_assets'))
        avg_ar  = _avg(ar,  prev.get('ar'))
        avg_inv = _avg(inv, prev.get('inventory'))
        avg_ppe = _avg(ppe, prev.get('ppe'))
        avg_eq  = _avg(eq,  prev.get('equity'))

        ie_abs = abs(ie) if ie is not None else 0
        ratios_list.append({
            'debt_ratio':     _safe_pct((ta or 0) - (eq or 0), ta),
            'lt_cap_ratio':   _safe_pct((ll or 0) + (eq or 0), ppe),
            'current_ratio':  _safe_pct(ca, cl),
            'quick_ratio':    _safe_pct((ca or 0) - (inv or 0), cl),
            'ar_turnover':    _safe_div(rev, avg_ar),
            'avg_coll_days':  _safe_div(365, _safe_div(rev, avg_ar)),
            'inv_turnover':   _safe_div(cogs, avg_inv),
            'avg_inv_days':   _safe_div(365, _safe_div(cogs, avg_inv)),
            'ppe_turnover':   _safe_div(rev, avg_ppe),
            'ta_turnover':    _safe_div(rev, avg_ta),
            'roa':            _safe_pct((ni or 0) + ie_abs * 0.75, avg_ta),
            'roe':            _safe_pct(ni, avg_eq),
            'pretax_capital': None,
            'gross_margin':   _safe_pct(gp, rev),
            'op_margin':      _safe_pct(oi, rev),
            'net_margin':     _safe_pct(ni, rev),
            'eps':            eps,
            'cf_ratio':       _safe_pct(cf_list[-1]['operating'], cl),
            'cf_adequacy':    None,
            'cf_reinvest':    None,
        })

    return company_name, currency, ratios_list, bs_list, cf_list


# ─────────────────────────────────────────────
#  Flask Routes
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return INDEX_HTML

@app.route('/report', methods=['POST'])
def report():
    stock_id     = request.form.get('stock_id', '').strip().upper()
    company_name = request.form.get('company_name', '').strip()
    years = [
        request.form.get('y1', '2023').strip(),
        request.form.get('y2', '2024').strip(),
        request.form.get('y3', '2025').strip(),
    ]
    ce_years = []
    for y in years:
        try:
            ce_years.append(int(y))
        except:
            pass
    if not ce_years:
        ce_years = [2023, 2024, 2025]

    if not stock_id:
        return INDEX_HTML

    currency = '百萬元'

    if not is_taiwan_stock(stock_id):
        # ── International path (yfinance) ──
        try:
            name, currency_code, ratios_list, bs_list, cf_list = \
                fetch_international_data(stock_id, ce_years)
            if not company_name:
                company_name = name
            currency = f'百萬 {currency_code}'
        except Exception as e:
            ratios_list = [{} for _ in ce_years]
            bs_list     = [{} for _ in ce_years]
            cf_list     = [{} for _ in ce_years]
    else:
        # ── Taiwan path (MOPS) ──
        session = req.Session()
        try:
            session.get('https://mops.twse.com.tw/mops/web/index',
                        headers=BROWSER_HEADERS, timeout=10)
        except:
            pass

        ratios_list, bs_list, cf_list = [], [], []
        for ce_year in ce_years:
            try:    ratios_list.append(fetch_ratios(session, stock_id, ce_year))
            except: ratios_list.append({})
            try:    bs_list.append(fetch_balance_sheet(session, stock_id, ce_year))
            except: bs_list.append({})
            try:    cf_list.append(fetch_cashflow(session, stock_id, ce_year))
            except: cf_list.append({})

        if not company_name:
            company_name = fetch_company_name(session, stock_id)

    html_out = report_page(
        stock_id, company_name,
        [str(y) for y in ce_years],
        ratios_list, bs_list, cf_list,
        currency
    )
    return Response(html_out, content_type='text/html; charset=utf-8')


@app.route('/debug/<stock_id>')
def debug(stock_id):
    """診斷頁面：顯示 MOPS 回傳內容與解析結果"""
    lines = [f'<h2>診斷：{stock_id}</h2><pre style="white-space:pre-wrap;font-size:12px">']
    session = req.Session()
    try:
        session.get('https://mops.twse.com.tw/mops/web/index',
                    headers=BROWSER_HEADERS, timeout=10)
        lines.append('✅ MOPS 首頁連線成功\n')
    except Exception as e:
        lines.append(f'❌ MOPS 首頁連線失敗: {e}\n')

    for ce_year in [2023, 2024, 2025]:
        roc = ce_to_roc(ce_year)
        lines.append(f'\n── {ce_year}年 (民國{roc}年) ──\n')
        try:
            raw = post_mops(session, 'ajax_t05st22', stock_id, roc)
            rows = parse_table_rows(raw)
            lines.append(f'  t05st22 回傳長度: {len(raw)} 字元，解析到 {len(rows)} 列\n')
            for label, vals in rows[:8]:
                lines.append(f'  {label[:30]:30s} | {vals[:3]}\n')
            ratios = fetch_ratios(session, stock_id, ce_year)
            lines.append(f'  解析結果: {ratios}\n')
        except Exception as e:
            lines.append(f'  ❌ 錯誤: {e}\n')

    lines.append('</pre>')
    return ''.join(lines)


if __name__ == '__main__':
    print('=' * 50)
    print('  財務比率報表產生器')
    print('  開啟瀏覽器，前往: http://localhost:5000')
    print('  診斷頁面: http://localhost:5000/debug/2330')
    print('  按 Ctrl+C 可停止程式')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
