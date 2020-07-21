from getpass import getpass
import os
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
# This script targets the /annotations/datasets API route.
#
# Even if launching this script for a local instance, keep
# the https of the host address and 'verify_ssl = False'
#
# This script includes a workaround for an import size problem with the API.
# Each file needed to contain less than 20k annotations, else it caused a
# 400 bad request. Even a "successful" requests returned a 502 Bad Gateway,
# but the annotations were still imported...
#
# Now, the features are bundled in smaller post requests and everything
# should work properly.
#
# The annotation file needs to be in geojson format.

 
#
# Change the values below for your needs
#
# Recommended to create a specific user before hand with the role of importer only
host_address = os.getenv("HOST_ADDRESS", "https://ip-address")
host_user = os.getenv("HOST_USER", "admin")
annotation_file = os.getenv("ANNOTATION_FILE", "file/path/and/name.geojson")
verify_ssl = False

# The step number can be played with, depending of your infrastructure
# 500 is the recommended value to prevent timeouts and other errors cited
# above
step = int(os.getenv("STEP_VALUE", 500))
if not step or not isinstance(step, int) or step < 1:
    print("Variable named step is not valid. Must be a number and higher than zero")
    exit()

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

# Open session
session = login(host_address, host_user)

# Fetch annotation file
with open(annotation_file, 'r') as f:
    data = f.read()
    print("Loading {}".format(annotation_file))
    annotations = json.loads(data)

# Dataset base attributes
features = annotations['features']
type = annotations['type']
crs = annotations['crs']
name = annotations['name']

# Loop attributes
new_payload = []
count = 0
num_annotation = len(annotations['features'])


for i in range(0, num_annotation, step):
    new_payload += features[i: i + step]
    dict = {
        'type': type,
        'crs': crs,
        'features': new_payload
    }
    r = session.post(
        f"{host_address}/api/v1/annotations/datasets", json=dict, verify=verify_ssl)
    r.raise_for_status()
    count += len(new_payload)
    new_payload = []

    print(f"\nRead {count} annotations out of {num_annotation}. Batch summary:")
    print(r.json())

print("All annotations have been written")