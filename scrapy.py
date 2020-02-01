import requests
import threading
import sched
import json
import datetime as dt
from tabulate import tabulate
from math import floor
import pickle
import time
import logging
import os
from display import DisplayDriver


logging.basicConfig(level=logging.DEBUG)

show_next_connections = 4
data_folder = "data/"

def fetch_data(url, file, lock):
    logging.debug("Fetched data at " +
                  str(dt.datetime.now().strftime("%H:%M:%S")) + "!")
    resp: requests.Response = requests.get(url)
    respObj = json.loads(resp.content)
    lock.acquire()
    pickle.dump(respObj, open(file, "w+b"))
    lock.release()

def start_data_fetch_thread(mvg_api, api_file, lock):
    data_fetcher = threading.Thread(
                target=fetch_data, args=(mvg_api, api_file, lock))
    data_fetcher.start()

def load_data(api_file, lock):
    lock.acquire()
    respObj = pickle.load(open(api_file, "rb"))
    lock.release()
    return respObj

def process_data(api_data):
    destination = api_data["destination"]
    cancelled = api_data["cancelled"]
    delayKey = "delay"
    live = True
    if delayKey in api_data.keys():
        delay = api_data["delay"]
    else:
        delay = 0
        live = False
    sev: bool = api_data["sev"]

    if not cancelled:
        seconds = floor((dt.datetime.fromtimestamp(floor(
            api_data["departureTime"]/1000)) - dt.datetime.now()).total_seconds()) + (delay * 60)
        if seconds > 0:
            minutes = floor(seconds / 60)
            secondsUnderSixty: str = seconds
            while seconds >= 60:
                seconds -= 60
                secondsUnderSixty = seconds
            departureTimeDisplay: str = str(
                minutes) + "m " + str(secondsUnderSixty) + "s"
        else:
            departureTimeDisplay = "Jetzt"
        if sev:
            destination += " SEV"
    else:
        departureTimeDisplay = "X"
    if live:
        delay = str(delay) + "m"
    else:
        delay = "Not Live"
    return destination, departureTimeDisplay, delay

def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)

def main():
    mvg_api = "https://www.mvg.de/api/fahrinfo/departure/de:09162:700"
    create_folder(data_folder)
    api_file = os.path.join(data_folder, "departures.p")
    lock = threading.Lock()
    content = list()
    fetch_data(mvg_api, api_file, lock)
    respObj = pickle.load(open(api_file, "rb"))
    display = DisplayDriver()
    i = 0
    refresh_counter = 0
    while True:
        if refresh_counter == 4:
            respObj = load_data(api_file, lock)
        if refresh_counter >= 45:
            start_data_fetch_thread(mvg_api, api_file, lock)
            refresh_counter = 0
        refresh_counter += 1
        for api_data in respObj["departures"]:
            destination, departure_time_display, delay = process_data(api_data)
            content.append([destination, departure_time_display, delay])
            i += 1
            if i > show_next_connections:
                break
        i = 0

        display.write_first_line("S8: " + str(content[0][1]))
        header = ["Richtung", "Minuten", "Verspätung"]
        print(tabulate(content, headers=header))
        print("")
        content = list()
        time.sleep(1)

if __name__ == "__main__":
    main()