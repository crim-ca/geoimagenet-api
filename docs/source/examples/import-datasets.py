from getpass import getpass
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
host_address = "https://geoimagenet.ca/"
host_user = "osm"
annotation_file = 'Annotations_OSM_All_3857.geojson'
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

for i, ft in enumerate(features):
    new_payload.append(ft)
    count += 1
    is_last_feature = i == num_annotation - 1
    if count == 500 or is_last_feature:
        dict = {
            'type': type,
            'crs': crs,
            'name': name,
            'features': new_payload
        }
        r = session.post(
            f"{host_address}/api/v1/annotations/datasets", json=dict, verify=verify_ssl
        )
        r.raise_for_status()
        count = 0
        new_payload = []

        print(f"\nRead {i + 1} annotations out of {num_annotation}. Batch summary:")
        print(r.json())

print("All annotations have been written")