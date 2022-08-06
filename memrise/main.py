import argparse
import json
import pandas as pd
import re
import requests
import shutil

from pathlib import Path
from pyquery import PyQuery as Element

_COLUMNS = [
    "Swedish",
    "English",
    "Definition",
    "Category",
    "Pronunciation",
    "Audio",
]
_FL_URL = "http://folkets-lexikon.csc.kth.se/folkets/service"
_SO_URL = "https://svenska.se/so"
_SO_SERVICE_URL = "https://isolve-so-service.appspot.com/pronounce"


def run(input, output):
    words = []
    queries = pd.read_csv(input, names=["Query"])["Query"]
    for query in queries:
        print("Slår upp ordet {}...".format(query))
        word = {**_read_so(query), **_read_fl(query)}
        print(json.dumps(word, ensure_ascii=False, indent=2))
        words.append(word)
    words = pd.DataFrame(data=words, columns=_COLUMNS, index=queries)
    words["Category"].fillna("okänd", inplace=True)
    for category in sorted(words["Category"].unique()):
        path = Path(output) / category
        path.mkdir(parents=True, exist_ok=True)
        chunk = words[words["Category"] == category]
        chunk.index.to_series().to_csv(path / "_index.csv", index=False)
        chunk[_COLUMNS[:-1]].to_csv(path / "_import.csv", index=False)
        for query, word in chunk[~chunk["Audio"].isnull()].iterrows():
            print("Laddar ner ljudet {}...".format(query))
            with requests.get(word["Audio"], stream=True) as response:
                with open(path / (query + ".mp3"), "wb") as file:
                    shutil.copyfileobj(response.raw, file)


def _read_fl(query):
    words = []
    response = requests.get(_FL_URL, params=dict(word=query))
    page = Element(response.text)
    for element in page.find("body > p"):
        word = {}
        element = Element(element)
        elements = element.find("img:first")
        if not elements or elements[0].get("alt") == "(Engelska)":
            continue
        elements = element.find('img[alt="(Svenska)"] + b')
        if elements:
            match = re.match(".*</b> (\w+),.*", str(elements))
            if match:
                word["Category"] = match.group(1)
            elements = map(lambda element: element.text, elements)
            word["Swedish"] = ", ".join(elements).replace("|", "")
        elements = element.find('img[alt="(Engelska)"] ~ b')
        if elements:
            elements = map(lambda element: element.text, elements)
            word["English"] = ", ".join(elements)
        elements = element.find('a[title="Ladda ner uttalet"]')
        if elements:
            word["Audio"] = elements[0].get("href")
        match = re.match(".*Uttal: (\[[^\[\]]+\]).*", element.outerHtml())
        if match:
            word["Pronunciation"] = match.group(1)
        words.append(word)
    if not words:
        return {}
    distances = [abs(len(word.get("Swedish", "")) - len(query)) for word in words]
    return words[distances.index(min(distances))]


def _read_so(query):
    words = []
    response = requests.get(
        _SO_URL,
        params=dict(sok=query),
        headers={"User-Agent": "curl/7.77.0"},
    )
    page = Element(response.text)
    for element in page.find("div.cshow a.slank"):
        if any(map(lambda text: text == query, element.text_content().split(" "))):
            match = re.match(".*id=(\d+).*", element.get("href"))
            if match:
                response = requests.get(
                    _SO_URL,
                    params=dict(id=match.group(1)),
                    headers={"User-Agent": "curl/7.77.0"},
                )
                page = Element(response.text)
                break
    for element in page.find("div.lemmalista"):
        word = {}
        element = Element(element)
        elements = element.find("span.orto")
        if elements:
            word["Swedish"] = elements[0].text
        elements = element.find("div.ordklass")
        if elements:
            word["Category"] = elements[0].text
        elements = element.find("span.def")
        if elements:
            word["Definition"] = (
                Element(elements[0]).text().replace("\u00ad", "").replace("\n", "")
            )
        elements = element.find("a.ljudfil")
        if elements:
            match = re.match("playAudioForLemma\('(.+)'\);", elements[0].get("onclick"))
            if match:
                word["Audio"] = _SO_SERVICE_URL + "?id={}.mp3".format(match.group(1))
        words.append(word)
    return next(iter(words), {})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    run(**vars(parser.parse_args()))
