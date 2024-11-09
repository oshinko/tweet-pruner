import datetime
import time
import traceback
import urllib.request

PRUNE_BATCH_SIZE = 50
WAIT_TIME = 1 * 60 * 60  # 15 分で十分なはずだがなんとなく蹴られてる気がするので十分に長い値にしてる

jst = datetime.timezone(datetime.timedelta(hours=9))
url = f'http://server/prune?limit={PRUNE_BATCH_SIZE}'

while True:
    try:
        with urllib.request.urlopen(url) as resp:
            resp_data = resp.read()
            print(datetime.datetime.now(tz=jst), resp_data)
    except Exception as e:
        tb = traceback.format_exc()
        print(datetime.datetime.now(tz=jst), tb)
        if hasattr(e, 'read'):
            print(e.headers)
            print(e.read().decode('utf8'))

    time.sleep(WAIT_TIME)
