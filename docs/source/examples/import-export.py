from getpass import getpass
import requests
import datetime

host_from = "https://geoimagenet.ca"
host_to = "https://geoimagenet.crim.ca"

verify_ssl = False


def login(host, username) -> requests.Session:
    login_url = f"{host}/magpie/signin"
    data = {
        "user_name": username,
        "password": getpass(f"Password for {host}: "),
        "provider": "ziggurat",
    }
    session = requests.Session()
    r = session.post(login_url, json=data, verify=verify_ssl)
    r.raise_for_status()

    return session


session_1 = login(host_from, "admin")
params = {"status": "validated"}

# if you want to filter by date
today = datetime.date.today().toordinal()
last_week = today - 7
last_week_sunday = datetime.datetime.fromordinal(last_week - (last_week % 7))
last_week_saturday = last_week_sunday + datetime.timedelta(days=6, hours=23, minutes=59)

params["last_updated_since"] = last_week_sunday
params["last_updated_before"] = last_week_saturday

r = session_1.get(f"{host_from}/api/v1/annotations", params=params, verify=verify_ssl)
r.raise_for_status()

annotations = r.json()
n_annotations = len(annotations["features"])

print(f"Received {n_annotations} annotations")

if n_annotations:
    session_2 = login(host_to, "admin")
    r = session_2.post(
        f"{host_to}/api/v1/annotations/import", json=annotations, verify=verify_ssl
    )
    r.raise_for_status()

    written_count = len(r.json())

    print(f"Written {written_count} annotations")
