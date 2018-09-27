#!/usr/bin/env python

import datetime
import os

import requests
from flask import Flask
from pybacklog import BacklogClient

import config

JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')

app = Flask(__name__)


def to_datetime(s: str) -> datetime:
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def date_format(s: str, f: str = '%Y-%m-%d') -> str:
    return to_datetime(s).strftime(f)


@app.route('/task/alert')
def daily_alert():
    client = BacklogClient(config.SPACE_NAME, config.API_KEY)
    # project_id = client.get_project_id()
    project_id = config.PROJECT_ID
    issues = client.issues({"projectId[]": [project_id], 'statusId[]': [1, 2, 3], "sort": "dueDate"})

    over_list = []
    today_list = []
    soon_list = []

    today = datetime.datetime.now(JST).replace(hour=0, minute=0, second=0)

    for x in issues:
        if x['dueDate'] is None:
            break

        due_date = to_datetime(x['dueDate'])

        delta = (due_date - today).days
        print(x['summary'], delta)
        if delta == 0:
            # 締め切り当日
            today_list.append(x)

        elif delta <= 7:
            # 1週間以内
            soon_list.append(x)

        elif delta < 0:
            # 期限切れ
            over_list.append(x)

    if len(over_list) > 0:
        payload = create_payload(over_list, '期限切れ', '#D00000')
        request_to_slack(payload)

    if len(today_list) > 0:
        payload = create_payload(today_list, '今日が期限', '#0084FD')
        request_to_slack(payload)

    # weeklyは月曜日のみ実行
    if today.weekday() != 0:
        return 'OK'

    if len(soon_list) > 0:
        payload = create_payload(soon_list, 'もうすぐ期限切れ', '#FDFB00')
        request_to_slack(payload)

    return 'OK'


def create_payload(issue_list: list, title: str, color: str) -> dict:
    """
    SlackにPOSTするPayloadを作成
    """
    value = ''
    for issue in issue_list:
        value += '- {} {}\n'.format(date_format(issue['dueDate']),
                                    issue['summary'])

    return {'text': '*{}*'.format(title),
            'attachments': [
                {'fallback': title,
                 'color': color,
                 'fields': [{'value': value,
                             'short': False}
                            ]}
            ]}


def request_to_slack(payload: dict):
    """
    Slackにリクエストを投げる
    """
    # 開発環境では実行しない
    if os.getenv('GAE_ENV', '').startswith('localdev'):
        return

    request_header = {'Content-type': 'application/json'}

    try:
        requests.post(config.SLACK_POST_URL,
                      json=payload,
                      headers=request_header)
    except Exception as e:
        print(e)


if __name__ == '__main__':
    app.run(debug=True)
