from getpass import getpass
import requests
import datetime
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Even if launching this script for local instances, keep
# the https of the host address and 'verify_ssl = False'
#
# This script includes a workaround for an import size problem with the API.
# Problems were similar to the /annotations/datasets route, so the
# same solution is applied here.
#
# The features are bundled in smaller post requests and everything
# should work properly.
 
 
#
# Change the values below for your needs
#
host_from = "https://ip-address"
host_from_user = "admin"

host_to = "https://ip-address"
host_to_user = "admin"

verify_ssl = False
annotation_status = "released"


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

# Dataset base attribute
features = annotations['features']
type = annotations['type']
crs = annotations['crs']
 
# Loop attributes
new_payload = []
count = 0
num_annotation = len(annotations['features'])
total_rejected = 0
batch_rejected = 0
error_msg = []

#
# POST request
#
session_2 = login(host_to, host_to_user)

# This loop is slow because of how the API haddles the import.
# If a single annotation has a non matching image id between GIN
# instances, it will reject the whole batch.
#
# If you are sure there will be no errors (identical instances, for example), 
# you can take inspiration from import-export-via-datasets.py and speed up 
# the process by packaging more annotations in each request
for i, ft in enumerate(features):
    new_payload.append(ft)
    count += 1
    is_last_feature = i == num_annotation -1
    dict = {
        'type': type,
        'crs': crs,
        'features': new_payload
    }
    r = session_2.post(
        f"{host_to}/api/v1/annotations/import", json=dict, verify=verify_ssl)
    r.raise_for_status()
    if not isinstance(r.json(), list):
        total_rejected += 1
        batch_rejected += 1
        error_msg.append(r.json()["detail"])
    new_payload = []
    
    # The count number can be played with, depending of your infrastructure, but will only
    # affect the display of information, not the speed
    if count == 500 or is_last_feature:
        count = 0
        print(f"Read {i + 1} annotations out of {num_annotation}, {batch_rejected} annotations have been rejected for the following reasons:")
        if batch_rejected > 0:
            print(list(set(error_msg)))
        batch_rejected = 0
        error_msg = []
 
print(f"All annotations have been read, {total_rejected} annotations have been rejected")