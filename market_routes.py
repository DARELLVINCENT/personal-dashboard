from flask import Blueprint, render_template, request, redirect, flash, make_response
from io import StringIO
import yfinance as yf

market_bp = Blueprint('market_bp', __name__)

@market_bp.route('/market_data')
def market_data():
    return render_template('market_data.html')

@market_bp.route('/download_yfinance', methods=['POST'])
def download_yfinance():
    ticker = request.form['ticker'].upper()
    timeframe = request.form['timeframe']
    period = request.form['period']
    
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=timeframe)
        
        if df.empty:
            flash(f"Data tidak ditemukan untuk ticker {ticker} dengan parameter tersebut.", "error")
            return redirect('/market_data')
            
        # Format dataframe to CSV
        si = StringIO()
        df.to_csv(si)
        
        response = make_response(si.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={ticker}_{timeframe}_{period}.csv"
        response.headers["Content-type"] = "text/csv"
        return response
    except Exception as e:
        flash(f"Terjadi kesalahan saat mengunduh data: {str(e)}", "error")
        return redirect('/market_data')
