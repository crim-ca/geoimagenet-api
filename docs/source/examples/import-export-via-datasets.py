from getpass import getpass
import os
import requests
import datetime
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Even if launching this script for local instances, keep
# the https of the host address and 'verify_ssl = False'
#
# This script includes a workaround for an import size problem with the API
# on the `annotations/datasets` route
#
# The features are bundled in smaller post requests and everything
# should work properly.
#
# This script is to be used when only the annotations basic information
# is to be conserved (without instance specific data), or if the 
# `import-export-via-import.py` script is not running properly. 
# The instances must, however, share the same taxonomy codes.
 
 
#
# Change the values below for your needs
#
host_from = os.getenv("HOST_FROM", "https://ip-address")
host_from_user = os.getenv("USER_FROM", "admin")

host_to = os.getenv("HOST_TO", "https://ip-address")
host_to_user = os.getenv("USER_TO", "admin")

annotation_status = os.getenv("STATUS", "validated")
verify_ssl = False

# The step number can be played with, depending of your infrastructure
# 500 is the recommended value to prevent timeouts and other errors cited
# above
step = int(os.getenv("STEP_VALUE", 500))
if not step or step < 1:
    print("Variable named step is not valid. Must be a number higher than zero")
    exit()


# Utility login function
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

#
# Main script
#
# Get annotations from first instance
session_1 = login(host_from, host_from_user)
params = {"status": annotation_status}

# if you want to filter by date
# today = datetime.date.today().toordinal()
# last_week = today - 7
# last_week_sunday = datetime.datetime.fromordinal(last_week - (last_week % 7))
# last_week_saturday = last_week_sunday + datetime.timedelta(days=6, hours=23, minutes=59)
# params["last_updated_since"] = last_week_sunday
# params["last_updated_before"] = last_week_saturday

# Getting annotation from source
r = session_1.get(f"{host_from}/api/v1/annotations",
                  params=params, verify=verify_ssl)

r.raise_for_status()

#
# Prepare data for POST request
#
annotations = r.json()

# Remove non-necessary keys
for ft in annotations["features"]:
    ft["properties"].pop("taxonomy_class_id")
    ft["properties"].pop("annotator_id")
    ft["properties"].pop("image_id")
    ft["properties"].pop("image_name")
    ft["properties"].pop("name")
    ft["properties"].pop("review_requested")
    ft["properties"].pop("status")
    ft["properties"].pop("updated_at")
    ft.pop("id")

# Dataset base attribute
features = annotations['features']
type = annotations['type']
crs = annotations['crs']
 
# Loop attributes
new_payload = []
count = 0
num_annotation = len(annotations['features'])

#
# POST request
#
session_2 = login(host_to, host_to_user)

for i in range(0, num_annotation, step):
    new_payload += features[i: i + step]
    dict = {
        'type': type,
        'crs': crs,
        'features': new_payload
    }
    r = session_2.post(
        f"{host_to}/api/v1/annotations/datasets", json=dict, verify=verify_ssl)
    r.raise_for_status()
    count += len(new_payload)
    new_payload = []

    print(f"\nRead {count} annotations out of {num_annotation}. Batch summary:")
    print(r.json())

print("All annotations have been read")