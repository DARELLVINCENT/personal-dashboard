from routers.forecast import get_forecast; import traceback;

try:
    res = get_forecast('BBCA.JK', 14, 'ARIMA')
    print('Success:', res.keys())
except Exception as e:
    print(f'Failed: {e}')
    traceback.print_exc()
