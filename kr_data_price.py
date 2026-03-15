"""
kr_data_price.py  v6.0
- get_price_data: FDR 기반 (기존 유지)
- get_investor_flow_data: KRX 공식 API 직접 호출 (pykrx 제거)
  KRX가 pykrx에 데이터를 제공하는 동일한 엔드포인트를 직접 사용
"""
import pandas as pd
import requests
import FinanceDataReader as fdr
from datetime import datetime, timedelta


def get_price_data(symbol):
    try:
        df = fdr.DataReader(symbol)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        rename_map = {}
        if "Open" not in df.columns and "시가" in df.columns:
            rename_map["시가"] = "Open"
        if "High" not in df.columns and "고가" in df.columns:
            rename_map["고가"] = "High"
        if "Low" not in df.columns and "저가" in df.columns:
            rename_map["저가"] = "Low"
        if "Close" not in df.columns and "종가" in df.columns:
            rename_map["종가"] = "Close"
        if "Volume" not in df.columns and "거래량" in df.columns:
            rename_map["거래량"] = "Volume"

        if rename_map:
            df = df.rename(columns=rename_map)

        needed = ["Open", "High", "Low", "Close", "Volume"]
        for col in needed:
            if col not in df.columns:
                return pd.DataFrame()

        return df[needed].dropna()

    except Exception:
        return pd.DataFrame()


def _krx_investor_flow(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    KRX data.krx.co.kr API 직접 호출로 투자자별 매매금액 조회.
    pykrx가 내부적으로 사용하는 동일한 엔드포인트.

    start/end: "YYYYMMDD" 형식
    반환: 날짜 인덱스, 컬럼: [금융투자, 보험, 투신, 사모, 은행, 기타금융, 연기금, 기관합계,
                              기타법인, 개인, 외국인합계, 기타외국인, 전체]
    """
    url = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://data.krx.co.kr/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    payload = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT02203",
        "locale": "ko_KR",
        "isuCd": symbol,
        "isuCd2": "",
        "strtDd": start,
        "endDd": end,
        "askBid": "3",        # 3 = 매수금액
        "detailView": "1",
        "csvxls_isNo": "false",
    }

    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("output") or data.get("OutBlock_1") or []
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # 날짜 컬럼
        date_col = next((c for c in ["TRD_DD", "일자", "날짜"] if c in df.columns), None)
        if date_col is None:
            return pd.DataFrame()

        df[date_col] = pd.to_datetime(df[date_col], format="%Y/%m/%d", errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col).sort_index()

        # 숫자 컬럼 변환
        for col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "").str.strip(),
                errors="coerce"
            )

        # 컬럼명 한글 매핑
        rename = {
            "TRDVAL1": "금융투자", "TRDVAL2": "보험", "TRDVAL3": "투신",
            "TRDVAL4": "사모",    "TRDVAL5": "은행", "TRDVAL6": "기타금융",
            "TRDVAL7": "연기금",  "TRDVAL8": "기관합계",
            "TRDVAL9": "기타법인","TRDVAL10": "개인",
            "TRDVAL11": "외국인합계", "TRDVAL12": "기타외국인",
            "TRDVAL13": "전체",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        return df

    except Exception:
        return pd.DataFrame()


def get_investor_flow_data(symbol: str, isu_cd: str = None) -> pd.DataFrame:
    """
    최근 370일 투자자별 매매금액 조회.
    KRX API는 ISU_CD(예: KR7005930003) 형식을 요구합니다.
    isu_cd가 없으면 symbol(종목코드)로 fallback 시도.
    KRX 직접 호출 → 실패 시 빈 DataFrame 반환.
    """
    end = datetime.today()
    start = end - timedelta(days=370)

    # ISU_CD 우선 사용, 없으면 symbol fallback
    krx_code = isu_cd if isu_cd else symbol

    df = _krx_investor_flow(
        krx_code,
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
    )

    return df
