import base64
import datetime
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
import wsgiref.simple_server

CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']
REDIRECT_URI = os.environ['REDIRECT_URI']
# offline.access を足すとリフレッシュトークンが得れる
SCOPE = 'tweet.read tweet.write users.read offline.access'

AUTH_ENDPOINT = 'https://x.com/i/oauth2/authorize'
TOKEN_ENDPOINT = 'https://api.x.com/2/oauth2/token'
TWEET_ENDPOINT = 'https://api.x.com/2/tweets'

TOKEN_INFO = 'data/token.json'
TWEETS = 'data/tweets.json'
PRUNE_RESULT = 'data/prune_result.txt'

default_headers = [('Access-Control-Allow-Origin', '*')]

statuses = {int(x.split(maxsplit=1)[0]): x.split(maxsplit=1)[1] for x in """
200 OK
204 No Content
302 Found
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
405 Method Not Allowed
429 Too Many Requests
""".strip().splitlines()}

workspace = pathlib.Path.cwd()

b64cred = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode('utf8')).decode('utf8')

jst = datetime.timezone(datetime.timedelta(hours=9))


def _respond(respond, status, headers=None):
    respond(f'{status} {statuses[status]}', default_headers + (headers or []))


def get_tweets():
    with (workspace / TWEETS).open(encoding='utf8') as f:
        data = sorted([x['tweet'] for x in json.load(f)],
                        key=lambda x: x['edit_info']['initial']['editableUntil'])
    reacted = [x for x in data if int(x['favorite_count']) > 0 or int(x['retweet_count']) > 0]
    no_reacted = [x for x in data if int(x['favorite_count']) == 0 and int(x['retweet_count']) == 0]
    print('all data', len(data))
    print('reacted', len(reacted))
    print('no-reacted', len(no_reacted))
    return data, reacted, no_reacted


def refresh_token():
    with (workspace / TOKEN_INFO).open(encoding='utf8') as f:
        token_info = json.load(f)

    data = urllib.parse.urlencode({
        'refresh_token': token_info['refresh_token'],
        'grant_type': 'refresh_token',
        # 'client_id': CLIENT_ID
    }).encode('utf8')
    request = urllib.request.Request(TOKEN_ENDPOINT, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + b64cred
    })

    try:
        with urllib.request.urlopen(request, data=data) as resp:
            token_info = json.load(resp)
    except Exception as e:
        raise Exception(e.read()) from e

    print('# refreshed token_info:', token_info)

    with (workspace / TOKEN_INFO).open('w') as f:
        json.dump(token_info, f, indent=2)

    return token_info


def _delete_tweet(access_token, tweet_id):
    request = urllib.request.Request(
        f'{TWEET_ENDPOINT}/{tweet_id}',
        headers={
            'Authorization': 'Bearer ' + access_token
        },
        method='DELETE'
    )
    with urllib.request.urlopen(request) as resp:
        x_headers = [(k, v) for k, v in resp.headers.items()
                     if k.startswith('x-')]
        return json.load(resp), x_headers


def app(environ, respond):
    path = environ['PATH_INFO']

    if path == '/':
        _respond(respond, 200, [('Content-Type', 'text/html')])
        return ["""
<!doctype html>
<html>
<head>
<meta charset="utf8">
</head>
<body>
<h1>Tweet Pruner</h1>
<ul>
  <li><a href="/authenticate">Authenticate</a></li>
  <li><a href="/prune">Prune tweets</a></li>
</ul>
</body>
</html>
""".lstrip().encode('utf8')]

    if path == '/tweets':
        data, reacted, no_reacted = get_tweets()
        qs = dict(urllib.parse.parse_qsl(environ['QUERY_STRING']))
        filter_ = qs.get('filter')
        if filter_ == 'reacted':
            target = reacted
        elif filter_ == 'no-reacted':
            target = no_reacted
        else:
            target = data
        items = ''.join(f"<tr><td>{i + 1}</td><td>{x['id']}</td><td>{x['edit_info']['initial']['editableUntil']}</td><td>{x['favorite_count']}</td><td>{x['retweet_count']}</td></tr>\n"
                        for i, x in enumerate(target))
        _respond(respond, 200, [('Content-Type', 'text/html')])
        return [f"""
<!doctype html>
<html>
<head>
<meta charset="utf8">
<style>
table {{
  border-collapse: collapse;
}}
th {{
  position: sticky;
  top:0;
  left: 0;
  z-index: 1;
  background-color: skyblue;
}}
th, td {{
  border: 1px solid black;
  padding: 8px;
}}
</style>
</head>
<body>
<table style="ta">
  <tr><th>No.</th><th>ID</th><th>Date</th><th>favorite_count</th><th>retweet_count</th></tr>
  {items}
</table>
</body>
</html>
""".lstrip().encode('utf8')]

    if path == '/authenticate':  # 認可 URL に遷移
        params = urllib.parse.urlencode({
            'response_type': 'code',
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'scope': SCOPE,
            'state': 'state',
            'code_challenge': 'challenge',
            'code_challenge_method': 'plain'
        })
        _respond(respond, 302, [('Location', AUTH_ENDPOINT + '?' + params)])
        return []

    if path == '/authorized':  # アクセストークンを取得する
        qs = dict(urllib.parse.parse_qsl(environ['QUERY_STRING']))
        print('authorization code', qs['code'])
        data = urllib.parse.urlencode({
            'code': qs['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'code_verifier': 'challenge',
            'client_id': CLIENT_ID
        }).encode('utf8')
        request = urllib.request.Request(TOKEN_ENDPOINT, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + b64cred
        })

        try:
            with urllib.request.urlopen(request, data=data) as resp:
                resp_item = json.load(resp)
                print(resp_item)
        except Exception as e:
            raise Exception(e.read()) from e

        with (workspace / TOKEN_INFO).open('w') as f:
            json.dump(resp_item, f, indent=2)

        _respond(respond, 200, [('Content-Type', 'text/html')])
        return ["""
<!doctype html>
<html>
<head>
<meta charset="utf8">
</head>
<body>
<p>Authentication succeeded!</p>
<ul>
  <li><a href="/prune">Prune tweets</a></li>
</ul>
</body>
</html>
""".lstrip().encode('utf8')]

    if path == '/prune':
        _, _, no_reacted = get_tweets()

        qs = dict(urllib.parse.parse_qsl(environ['QUERY_STRING']))
        try:
            # あまり値が大きいとリフレッシュトークンの期限が切れるので注意
            limit = int(qs['limit'])
        except (KeyError, ValueError):
            limit = None

        output_file = workspace / PRUNE_RESULT
        if output_file.exists():
            with output_file.open() as f:
                for line in f:
                    last_id, _ = line.split(' ', 1)
                    last_id = int(last_id)

        else:
            last_id = 0

        # リフレッシュトークンの期限切れが早いので、毎回リフレッシュ
        try:
            token_info = refresh_token()
        except Exception as e:
            if not hasattr(e, 'status'):
                raise Exception(e.read()) from e
            # あり得るエラー一覧
            # - 401 Unauthorized: アクセストークン及びリフレッシュトークン期限切れ
            _respond(respond, e.status)
            return [e.read()]

        with output_file.open('a') as out_f:
            n_tweets_deleted = 0

            for i, tweet in enumerate(no_reacted):
                if int(tweet['id']) <= last_id:
                    continue

                if limit and limit <= n_tweets_deleted:
                    break

                # if i + 1 + 50 > len(no_reacted):
                #     break

                try:
                    result = _delete_tweet(token_info['access_token'], tweet['id'])
                except Exception as e:
                    print('# deleted tweets:', n_tweets_deleted)

                    if not hasattr(e, 'status'):
                        raise Exception(e.read()) from e

                    # あり得るエラー一覧
                    # - 429 Too Many Requests: API レートエラー
                    headers = [(k, v) for k, v in e.headers.items()
                                if k.startswith('x-')]
                    _respond(respond, e.status, headers)
                    return [e.read()]

                print(tweet['id'], datetime.datetime.now(tz=jst), result, file=out_f)
                n_tweets_deleted += 1

        print('# deleted tweets:', n_tweets_deleted)
        _respond(respond, 200)
        return [b'OK!']


    _respond(respond, 404)
    return []


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    httpd = wsgiref.simple_server.make_server('', port, app)
    print(f'Serving {workspace} on port {port}, control-C to stop')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down.')
        httpd.server_close()
