from datetime import datetime, timezone

import os.path
import ast
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
print("Введите дедлайн (2026.06.13)")
a = list(map(int, input().split(".")))
#if not os.path.exists('token.json'):
print("Со скольки до скольки вы готовы работать? (10:00-23:00)")
b = list(map(str, input().split("-")))
print("Сколько занимает дорога до университета? (60)")
c = int(input())
with open ("time.txt", "w", encoding="utf-8") as f:
    f.write("{" + f"'beginning': '{b[0]}', 'ending': '{b[1]}', 'road': {c}" + "}")

slevents = {}

with open("time.txt", "r", encoding="utf-8") as file:
    content = file.read()
data_dict = ast.literal_eval(content)
beginning = data_dict["beginning"]
ending = data_dict["ending"]
road = data_dict["road"]
def google_auth():

    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)

            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def get_events_until(date_limit):

    creds = google_auth()

    service = build('calendar', 'v3', credentials=creds)

    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    time_max = date_limit.isoformat() + 'Z'

    events_result = service.events().list(calendarId='primary', timeMin=now, timeMax=time_max, singleEvents=True, orderBy='startTime').execute()

    events = events_result.get('items', [])

    return events


def time_to_minutes(time_str):

    hours, minutes = map(int, time_str.split(':'))

    return hours * 60 + minutes


def minutes_to_time(minutes):

    hours = minutes // 60
    mins = minutes % 60

    return f"{hours:02}:{mins:02}"


def create_slevents(events):

    if not events:
        print("Событий нет")
        return

    for event in events:

        start = event['start'].get('dateTime',event['start'].get('date'))
        end = event['end'].get('dateTime',event['end'].get('date'))
        title = event.get('summary', 'Без названия')
        
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))

        day = start_dt.strftime('%d.%m')
        event_time = start_dt.strftime('%H:%M') + "-" + end_dt.strftime('%H:%M')
        
        if start_dt.strftime('%d.%m') not in slevents:
            slevents[start_dt.strftime('%d.%m')] = []
        if event_time not in slevents[day]:
            slevents[day].append(event_time)
    for day in slevents:
        if len(slevents[day]) == 1:
            startoflessons, endoflessons = slevents[day][0].split('-')
            start = minutes_to_time(time_to_minutes(startoflessons) - road)
            end = minutes_to_time(time_to_minutes(endoflessons) + road)
            slevents[day][0] = f"{start}-{end}"
        if len(slevents[day]) > 1:
            startoflessons, endoflessons = slevents[day][0][:5], slevents[day][len(slevents[day]) - 1][6:]
            start = minutes_to_time(time_to_minutes(startoflessons) - road)
            end = minutes_to_time(time_to_minutes(endoflessons) + road)
            slevents[day][0] = f"{start}-{slevents[day][0][6:]}"
            slevents[day][len(slevents[day]) - 1] = f"{slevents[day][-1][:5]}-{end}"
    print(slevents)


def main():

    limit = datetime(a[0], a[1], a[2])
    events = get_events_until(limit)
    create_slevents(events)


if __name__ == '__main__':
    main()
