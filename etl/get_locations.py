import os

import pandas as pd
from openaq import OpenAQ
from dotenv import load_dotenv

load_dotenv()

OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")


def get_locations(client_open_aq, sensor_list, page, country_id):
    print("start while")
    while True:
        print(f"Page: {page}")
        locations = client_open_aq.locations.list(countries_id=country_id, page=page)
        sensor_list.extend(locations.results)
        if len(locations.results) == 0:
            break
        page += 1


locations = ["Katowice", "Kędzierzyn-Koźle", "Rybnik", "Racibórz", "Ostrava", "Żory", "Jastrzębie-Zdrój",
             "Wodzisław Śląski", "Gliwice", "Kraków", "Zabrze", "Sosnowiec", ]
poland_sensors_list = []
start_page = 1
try:
    client = OpenAQ(api_key=OPENAQ_API_KEY)
    get_locations(client, poland_sensors_list, start_page, 77)
except ConnectionError:
    print("Connection Error")

locations_df = pd.DataFrame(poland_sensors_list)
locations_list = locations_df.loc[locations_df['locality'].isin(locations), ["id", "name"]]
locations_list.to_csv("../data/location_list.csv", columns=["id", "name"], index=False, header=False, sep=";")

print("Sensor ids was saved.")
