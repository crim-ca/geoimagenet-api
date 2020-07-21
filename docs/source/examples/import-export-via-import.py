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
# This script includes a workaround for an import size problem with the API.
# Problems were similar to the /annotations/datasets route, so the
# same solution is applied here.
#
# The features are bundled in smaller post requests and everything
# should work properly.
#
# However, depending on the versions of each instances used in a transfert, the `/annotations/import`
# route can cause problems. For exemple, if the images are not from the same database or server.
# The consequences of these differences can be false negatives (more rejected annotations) to 
# outright failure of the whole process.
#
# Instead, you can use the `/annotations/datasets` route ( see import-export-via-datasets.py script).
 
 
#
# Change the values below for your needs
#
#
host_from = os.getenv("HOST_FROM", "https://ip-address")
host_from_user = os.getenv("USER_FROM", "admin")

host_to = os.getenv("HOST_TO", "https://ip-address")
host_to_user = os.getenv("USER_TO", "admin")

annotation_status = os.getenv("STATUS", "validated")
verify_ssl = False

# The main loop of this script is slow because of how the API haddles the import.
# If a single annotation has a non matching image id between GIN
# instances, it will reject the whole batch.
#
# If you are sure there will be no errors (identical instances, for example), 
# you can set "step" to a higher number in order to process the annotations in batches
# instead of individually.
#
# A value above 500 is likely to cause errors as cited above.
step = int(os.getenv("STEP_VALUE", 1))
if not step or not isinstance(step, int) or step < 1:
    print("Variable named step is not valid. Must be a number and higher than zero")
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

# Dataset base attribute
features = annotations['features']
type = annotations['type']
crs = annotations['crs']
 
# Loop attributes
new_payload = []
count = 0
num_annotation = len(annotations['features'])
batch_num = 0
total_annotations_rejected = 0
batch_annotations_rejected = 0
error_msg = []

#
# POST request
#
session_2 = login(host_to, host_to_user)

count_step = 500
batch_msg = f"\nProcessing annotations individually, showing result in batches of {count_step}:"
if step > 1:
    count_step = step
    batch_msg = f"\nProcessing annotations in batches of {count_step}"

print(batch_msg)

for i in range(0, num_annotation, step):
    new_payload += features[i: i + step]
    count += len(new_payload)
    is_last_feature = count == num_annotation
    dict = {
        'type': type,
        'crs': crs,
        'features': new_payload
    }
    r = session_2.post(
        f"{host_to}/api/v1/annotations/import", json=dict, verify=verify_ssl)
    r.raise_for_status()
    
    if not isinstance(r.json(), list):
        total_annotations_rejected += 1
        batch_annotations_rejected += 1
        error_msg.append(r.json()["detail"])
    new_payload = []

    if count % count_step == 0 or is_last_feature:

        msg = f"\nRead {count} annotations out of {num_annotation}"
        fail_msg = f"{batch_annotations_rejected} annotations of this batch have been rejected have been rejected for the following reason(s):"
        exit_message = f"All annotations have been read, {total_annotations_rejected} annotations have been rejected"

        if step > 1:
            msg = f"\nRead {count} annotations out of {num_annotation}."
            fail_msg = "At least one annotation has been rejected, causing this batch to fail for the following reason(s):"
            exit_message = f"All annotations have been read, {total_annotations_rejected} batches have been rejected out of {len(range(0, num_annotation, step))}."

        print(msg)
        if batch_annotations_rejected > 0:
            print(fail_msg)
            print(list(set(error_msg)))

        batch_annotations_rejected = 0
        error_msg = []
 
print(exit_message)