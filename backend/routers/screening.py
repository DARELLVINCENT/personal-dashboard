"""
Stock Screening Router — scans IHSG stocks against technical/fundamental filters.
Supports:
  - Full Scan (all .JK tickers fetched from IDX)
  - Demo (10 blue-chip stocks)
  - Manual watchlist
Uses ThreadPoolExecutor for parallel yfinance fetching and SSE streaming.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from typing import List, Optional, Literal
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import pandas as pd
import numpy as np
import requests as req
import json
import io
import time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screening", tags=["Screening"])

# ---------------------------------------------------------------------------
# Ticker Lists
# ---------------------------------------------------------------------------
DEMO_TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM",
    "ASII", "GOTO", "AMMN", "BREN", "BYAN",
]

# Cache for full ticker list (refreshes every 24 h)
_ticker_cache: dict = {"tickers": [], "fetched_at": 0}
CACHE_TTL = 86400  # 24 hours


def fetch_all_ihsg_tickers() -> List[str]:
    """Return the complete 957 tickers list."""
    return _FALLBACK_TICKERS[:]

# Complete IDX-listed tickers (as of mid-2026, sourced from Wikipedia)
_FALLBACK_TICKERS = sorted([
    "AADI","AALI","ABBA","ABDA","ABMM","ACES","ACRO","ACST","ADCP","ADES","ADHI","ADMF","ADMG","ADMR","ADRO","AEGS","AGAR","AGII","AGRO","AGRS","AHAP","AIMS","AISA","AKKU","AKPI","AKRA","AKSI","ALDO","ALII","ALKA","ALMI","ALTO","AMAG","AMAN","AMAR","AMFG","AMIN","AMMN","AMMS","AMOR","AMRT","ANDI","ANJT","ANTM","APEX","APIC","APII","APLI","APLN","ARCI","AREA","ARGO","ARII","ARKA","ARKO","ARMY","ARNA","ARTA","ARTI","ARTO","ASBI","ASDM","ASGR","ASHA","ASII","ASJT","ASLC","ASLI","ASMI","ASPI","ASPR","ASRI","ASRM","ASSA","ATAP","ATIC","ATLA","AUTO","AVIA","AWAN","AXIO","AYAM","AYLS","BABP","BABY","BACA","BAIK","BAJA","BALI","BANK","BAPA","BAPI","BATA","BATR","BAUT","BAYU","BBCA","BBHI","BBKP","BBLD","BBMD","BBNI","BBRI","BBRM","BBSI","BBSS","BBTN","BBYB","BCAP","BCIC","BCIP","BDKR","BDMN","BEBS","BEEF","BEER","BEKS","BELI","BELL","BESS","BEST","BFIN","BGTG","BHAT","BHIT","BIKA","BIKE","BIMA","BINA","BINO","BIPI","BIPP","BIRD","BISI","BJBR","BJTM","BKDP","BKSL","BKSW","BLES","BLOG","BLTA","BLTZ","BLUE","BMAS","BMBL","BMHS","BMRI","BMSR","BMTR","BNBA","BNBR","BNGA","BNII","BNLI","BOAT","BOBA","BOGA","BOLA","BOLT","BOSS","BPFI","BPII","BPTR","BRAM","BREN","BRIS","BRMS","BRNA","BRPT","BRRC","BSBK","BSDE","BSIM","BSML","BSSR","BSWD","BTEK","BTEL","BTON","BTPN","BTPS","BUAH","BUDI","BUKA","BUKK","BULL","BUMI","BUVA","BVIC","BWPT","BYAN","CAKK","CAMP","CANI","CARE","CARS","CASA","CASH","CASS","CBDK","CBMF","CBPE","CBRE","CBUT","CCSI","CDIA","CEKA","CENT","CFIN","CGAS","CHEK","CHEM","CHIP","CINT","CITA","CITY","CLAY","CLEO","CLPI","CMNP","CMNT","CMPP","CMRY","CNKO","CNMA","CNTX","COAL","COCO","COIN","COWL","CPIN","CPRI","CPRO","CRAB","CRSN","CSAP","CSIS","CSMI","CSRA","CTBN","CTRA","CTTH","CUAN","CYBR","DAAZ","DADA","DART","DATA","DAYA","DCII","DEAL","DEFI","DEPO","DEWA","DEWI","DFAM","DGIK","DGNS","DGWG","DIGI","DILD","DIVA","DKFT","DKHH","DLTA","DMAS","DMMX","DMND","DNAR","DNET","DOID","DOOH","DOSS","DPNS","DPUM","DRMA","DSFI","DSNG","DSSA","DUCK","DUTI","DVLA","DWGL","DYAN","EAST","ECII","EDGE","EKAD","ELIT","ELPI","ELSA","ELTY","EMAS","EMDE","EMTK","ENAK","ENRG","ENVY","ENZO","EPAC","EPMT","ERAA","ERAL","ERTX","ESIP","ESSA","ESTA","ESTI","ETWA","EURO","EXCL","FAPA","FAST","FASW","FILM","FIMP","FIRE","FISH","FITT","FLMC","FMII","FOLK","FOOD","FORE","FORU","FPNI","FUJI","FUTR","FWCT","GAMA","GDST","GDYR","GEMA","GEMS","GGRM","GGRP","GHON","GIAA","GJTL","GLOB","GLVA","GMFI","GMTD","GOLD","GOLF","GOLL","GOOD","GOTO","GPRA","GPSO","GRIA","GRPH","GRPM","GSMF","GTBO","GTRA","GTSI","GULA","GUNA","GWSA","GZCO","HADE","HAIS","HAJJ","HALO","HATM","HBAT","HDFA","HDIT","HEAL","HELI","HERO","HEXA","HGII","HILL","HITS","HKMU","HMSP","HOKI","HOME","HOMI","HOPE","HOTL","HRME","HRTA","HRUM","HUMI","HYGN","IATA","IBFN","IBOS","IBST","ICBP","ICON","IDEA","IDPR","IFII","IFSH","IGAR","IIKP","IKAI","IKAN","IKBI","IKPM","IMAS","IMJS","IMPC","INAF","INAI","INCF","INCI","INCO","INDF","INDO","INDR","INDS","INDX","INDY","INET","INKP","INOV","INPC","INPP","INPS","INRU","INTA","INTD","INTP","IOTF","IPAC","IPCC","IPCM","IPOL","IPPE","IPTV","IRRA","IRSX","ISAP","ISAT","ISEA","ISSP","ITIC","ITMA","ITMG","JARR","JAST","JATI","JAWA","JAYA","JECC","JGLE","JIHD","JKON","JMAS","JPFA","JRPT","JSKY","JSMR","JSPT","JTPE","KAEF","KAQI","KARW","KAYU","KBAG","KBLI","KBLM","KBLV","KBRI","KDSI","KDTN","KEEN","KEJU","KETR","KIAS","KICI","KIJA","KING","KINO","KIOS","KJEN","KKES","KKGI","KLAS","KLBF","KLIN","KMDS","KMTR","KOBX","KOCI","KOIN","KOKA","KONI","KOPI","KOTA","KPIG","KRAS","KREN","KRYA","KSIX","KUAS","LABA","LABS","LAJU","LAND","LAPD","LCGP","LCKM","LEAD","LFLO","LIFE","LINK","LION","LIVE","LMAS","LMAX","LMPI","LMSH","LOPI","LPCK","LPGI","LPIN","LPKR","LPLI","LPPF","LPPS","LRNA","LSIP","LTLS","LUCK","LUCY","MABA","MAGP","MAHA","MAIN","MANG","MAPA","MAPB","MAPI","MARI","MARK","MASB","MAXI","MAYA","MBAP","MBMA","MBSS","MBTO","MCAS","MCOL","MCOR","MDIA","MDIY","MDKA","MDKI","MDLA","MDLN","MDRN","MEDC","MEDS","MEGA","MEJA","MENN","MERI","MERK","META","MFMI","MGLV","MGNA","MGRO","MHKI","MICE","MIDI","MIKA","MINA","MINE","MIRA","MITI","MKAP","MKNT","MKPI","MKTR","MLBI","MLIA","MLPL","MLPT","MMIX","MMLP","MNCN","MOLI","MORA","MPIX","MPMX","MPOW","MPPA","MPRO","MPXL","MRAT","MREI","MSIE","MSIN","MSJA","MSKY","MSTI","MTDL","MTEL","MTFN","MTLA","MTMH","MTPS","MTRA","MTSM","MTWI","MUTU","MYOH","MYOR","MYTX","NAIK","NANO","NASA","NASI","NATO","NAYZ","NCKL","NELY","NEST","NETV","NFCX","NICE","NICK","NICL","NIKL","NINE","NIRO","NISP","NOBU","NPGF","NRCA","NSSS","NTBK","NUSA","NZIA","OASA","OBAT","OBMD","OCAP","OILS","OKAS","OLIV","OMED","OMRE","OPMS","PACK","PADA","PADI","PALM","PAMG","PANI","PANR","PANS","PART","PBID","PBRX","PBSA","PCAR","PDES","PDPP","PEGE","PEHA","PEVE","PGAS","PGEO","PGJO","PGLI","PGUN","PICO","PIPA","PJAA","PJHB","PKPK","PLAN","PLAS","PLIN","PMJS","PMMP","PMUI","PNBN","PNBS","PNGO","PNIN","PNLF","PNSE","POLA","POLI","POLL","POLU","POLY","POOL","PORT","POSA","POWR","PPGL","PPRE","PPRI","PPRO","PRAY","PRDA","PRIM","PSAB","PSAT","PSDN","PSGO","PSKT","PSSI","PTBA","PTDU","PTIS","PTMP","PTMR","PTPP","PTPS","PTPW","PTRO","PTSN","PTSP","PUDP","PURA","PURE","PURI","PWON","PYFA","PZZA","RAAM","RAFI","RAJA","RALS","RANC","RATU","RBMS","RCCC","RDTX","REAL","RELF","RELI","RGAS","RICY","RIGS","RIMO","RISE","RLCO","RMKE","RMKO","ROCK","RODA","RONY","ROTI","RSCH","RSGK","RUIS","RUNS","SAFE","SAGE","SAME","SAMF","SAPX","SATU","SBAT","SBMA","SCCO","SCMA","SCNP","SCPI","SDMU","SDPC","SDRA","SEMA","SFAN","SGER","SGRO","SHID","SHIP","SICO","SIDO","SILO","SIMA","SIMP","SINI","SIPD","SKBM","SKLT","SKRN","SKYB","SLIS","SMAR","SMBR","SMCB","SMDM","SMDR","SMGA","SMGR","SMIL","SMKL","SMKM","SMLE","SMMA","SMMT","SMRA","SMRU","SMSM","SNLK","SOCI","SOFA","SOHO","SOLA","SONA","SOSS","SOTS","SOUL","SPMA","SPRE","SPTO","SQMI","SRAJ","SRIL","SRSN","SRTG","SSIA","SSMS","SSTM","STAA","STAR","STRK","STTP","SUGI","SULI","SUNI","SUPA","SUPR","SURE","SURI","SWAT","SWID","TALF","TAMA","TAMU","TAPG","TARA","TAXI","TAYS","TBIG","TBLA","TBMS","TCID","TCPI","TDPM","TEBE","TECH","TELE","TFAS","TFCO","TGKA","TGRA","TGUK","TIFA","TINS","TIRA","TIRT","TKIM","TLDN","TLKM","TMAS","TMPO","TNCA","TOBA","TOOL","TOPS","TOSK","TOTL","TOTO","TOWR","TOYS","TPIA","TPMA","TRAM","TRGU","TRIL","TRIM","TRIN","TRIO","TRIS","TRJA","TRON","TRST","TRUE","TRUK","TRUS","TSPC","TUGU","TYRE","UANG","UCID","UDNG","UFOE","ULTJ","UNIC","UNIQ","UNIT","UNSP","UNTD","UNTR","UNVR","URBN","UVCR","VAST","VERN","VICI","VICO","VINS","VISI","VIVA","VKTR","VOKS","VRNA","VTNY","WAPO","WBSA","WEGE","WEHA","WGSH","WICO","WIDI","WIFI","WIIM","WIKA","WINE","WINR","WINS","WIRG","WMPP","WMUU","WOMF","WOOD","WOWS","WSBP","WSKT","WTON","YELO","YOII","YPAS","YULE","YUPI","ZATA","ZBRA","ZINC","ZONE","ZYRX",
])


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class FilterParams(BaseModel):
    ma50: Literal["above", "below", "ignore"] = "ignore"
    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    min_volume: Optional[float] = None
    max_pe: Optional[float] = None


class ScanRequest(BaseModel):
    mode: Literal["full", "demo", "manual"]
    tickers: Optional[List[str]] = []
    filters: FilterParams


class ExportRequest(BaseModel):
    passed: list
    failed: list


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------
def calculate_rsi(closes: pd.Series, window: int = 14) -> float:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1] if not rsi.empty else 0
    return float(val) if not pd.isna(val) else 0


def fetch_and_evaluate(ticker_code: str, filters: FilterParams) -> dict:
    """Download price data for *one* stock and evaluate it against filters."""
    jk = ticker_code if ticker_code.endswith(".JK") else f"{ticker_code}.JK"
    clean = ticker_code.replace(".JK", "")
    try:
        df = yf.download(jk, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 2:
            return {"ticker": clean, "passed": False,
                    "reasons": ["Data tidak ditemukan atau tidak cukup"],
                    "price": None, "ma50": None, "rsi": None, "volume": None, "pe_ratio": None}

        # Flatten multi-index columns (yfinance quirk)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(jk, axis=1, level=1, drop_level=True)

        current_price = float(df["Close"].iloc[-1])
        current_volume = float(df["Volume"].iloc[-1])
        ma50 = float(df["Close"].rolling(window=50, min_periods=10).mean().iloc[-1])
        rsi = calculate_rsi(df["Close"])

        # P/E ratio (fast_info is quicker than .info for most fields)
        try:
            info = yf.Ticker(jk).info
            pe_ratio = info.get("trailingPE", None)
        except Exception:
            pe_ratio = None

        # Evaluate filters
        passed = True
        reasons: List[str] = []

        if filters.ma50 == "above" and current_price < ma50:
            passed = False
            reasons.append(f"Harga ({current_price:,.0f}) di bawah MA50 ({ma50:,.0f})")
        elif filters.ma50 == "below" and current_price > ma50:
            passed = False
            reasons.append(f"Harga ({current_price:,.0f}) di atas MA50 ({ma50:,.0f})")

        if filters.rsi_min is not None and rsi < filters.rsi_min:
            passed = False
            reasons.append(f"RSI ({rsi:.1f}) di bawah minimum ({filters.rsi_min})")
        if filters.rsi_max is not None and rsi > filters.rsi_max:
            passed = False
            reasons.append(f"RSI ({rsi:.1f}) di atas maksimum ({filters.rsi_max})")

        if filters.min_volume is not None and current_volume < filters.min_volume:
            passed = False
            reasons.append(f"Volume ({current_volume:,.0f}) di bawah minimum ({filters.min_volume:,.0f})")

        if filters.max_pe is not None:
            if pe_ratio is None or (isinstance(pe_ratio, float) and np.isnan(pe_ratio)):
                passed = False
                reasons.append("P/E Ratio tidak tersedia")
            elif pe_ratio > filters.max_pe:
                passed = False
                reasons.append(f"P/E ({pe_ratio:.2f}) di atas maksimum ({filters.max_pe})")

        return {
            "ticker": clean, "price": current_price, "ma50": ma50,
            "rsi": rsi, "volume": current_volume, "pe_ratio": pe_ratio,
            "passed": passed, "reasons": reasons,
        }
    except Exception as e:
        return {"ticker": clean, "passed": False,
                "reasons": [f"Error: {str(e)}"],
                "price": None, "ma50": None, "rsi": None, "volume": None, "pe_ratio": None}


def _resolve_tickers(request: ScanRequest) -> List[str]:
    if request.mode == "manual":
        return [t.strip().upper().replace(".JK", "") for t in (request.tickers or []) if t.strip()]
    if request.mode == "demo":
        return DEMO_TICKERS[:]
    # full
    return fetch_all_ihsg_tickers()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/tickers")
def get_ticker_list():
    """Return the full list of available IHSG tickers (useful for UI count)."""
    tickers = fetch_all_ihsg_tickers()
    return {"count": len(tickers), "tickers": tickers}


@router.post("/scan_stream")
def scan_stream(request: ScanRequest):
    """
    SSE streaming endpoint — emits one JSON event per stock as it completes.
    Uses ThreadPoolExecutor to scan up to 8 stocks in parallel.
    """
    tickers = _resolve_tickers(request)
    filters = request.filters

    def _generate():
        # Send initial metadata
        yield f"data: {json.dumps({'type': 'start', 'total': len(tickers)})}\n\n"

        completed = 0
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_to_ticker = {
                pool.submit(fetch_and_evaluate, t, filters): t for t in tickers
            }
            for future in as_completed(future_to_ticker):
                completed += 1
                result = future.result()
                result["type"] = "result"
                result["progress"] = completed
                result["total"] = len(tickers)
                yield f"data: {json.dumps(result)}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'total': len(tickers)})}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.post("/scan")
def scan_stocks(request: ScanRequest):
    """Synchronous scan (kept for backward compat / small lists)."""
    tickers = _resolve_tickers(request)
    passed, failed = [], []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_and_evaluate, t, request.filters): t for t in tickers}
        for f in as_completed(futures):
            r = f.result()
            (passed if r["passed"] else failed).append(r)

    return {"passed": passed, "failed": failed, "total_scanned": len(tickers)}


@router.post("/export_excel")
def export_excel(request: ExportRequest):
    try:
        passed_df = pd.DataFrame(request.passed)
        failed_df = pd.DataFrame(request.failed)

        if not failed_df.empty and "reasons" in failed_df.columns:
            failed_df["reasons"] = failed_df["reasons"].apply(
                lambda x: ", ".join(x) if isinstance(x, list) else x
            )

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            (passed_df if not passed_df.empty
             else pd.DataFrame([{"Message": "Tidak ada saham yang lolos"}])
             ).to_excel(w, sheet_name="Lolos Filter", index=False)

            (failed_df if not failed_df.empty
             else pd.DataFrame([{"Message": "Tidak ada saham yang gagal"}])
             ).to_excel(w, sheet_name="Gagal Filter", index=False)

        buf.seek(0)
        return Response(
            buf.read(),
            headers={"Content-Disposition": 'attachment; filename="screening_results.xlsx"'},
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
