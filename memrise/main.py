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
    queries = pd.DataFrame(list(map(_to_query, queries)))
    for _, query in queries.iterrows():
        print(f"Slår upp {query.to_dict()}...")
        word = {**_read_so(query), **_read_fl(query)}
        print(json.dumps(word, ensure_ascii=False, indent=2))
        words.append(word)
    words = pd.DataFrame(data=words, columns=_COLUMNS, index=queries["Index"])
    words["Category"].fillna("okänd", inplace=True)
    for category in sorted(words["Category"].unique()):
        path = Path(output) / category
        path.mkdir(parents=True, exist_ok=True)
        words_ = words[words["Category"] == category]
        words_.index.to_series().to_csv(path / "_index.csv", index=False)
        words_[_COLUMNS[:-1]].to_csv(path / "_import.csv", index=False)
        for index, word in words_[~words_["Audio"].isnull()].iterrows():
            print(f"Laddar ner {index}...")
            with requests.get(word["Audio"], stream=True) as response:
                with open(path / (index + ".mp3"), "wb") as file:
                    shutil.copyfileobj(response.raw, file)


def _read_fl(query):
    words = []
    response = requests.get(_FL_URL, params=dict(word=query["Word"]))
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
        if query["Category"] and query["Category"] != word["Category"]:
            continue
        words.append(word)
    if not words:
        return {}
    distances = [
        abs(len(word.get("Swedish", "")) - len(query["Word"])) for word in words
    ]
    return words[distances.index(min(distances))]


def _read_so(query):
    mapping = {
        "subst.": "substantiv",
    }

    def _normalize(token):
        token = re.sub("^\d+", "", token)
        return mapping.get(token, token)

    def _tokenize(text):
        return list(filter(lambda token: token, map(_normalize, text.split(" "))))

    words = []
    response = requests.get(
        _SO_URL,
        params=dict(sok=query["Word"]),
        headers={"User-Agent": "curl/7.77.0"},
    )
    page = Element(response.text)
    for element in page.find("div.cshow a.slank"):
        tokens = _tokenize(element.text_content())
        if not any(map(query["Word"].__eq__, tokens)):
            continue
        if query["Category"] and not any(map(query["Category"].__eq__, tokens)):
            continue
        match = re.match(".*id=([_\d]+).*", element.get("href"))
        if not match:
            continue
        response = requests.get(
            _SO_URL,
            params=dict(id=match.group(1)),
            headers={"User-Agent": "curl/7.77.0"},
        )
        page = Element(response.text)
        break
    for element in page.find("div.superlemma"):
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
                word["Audio"] = f"{_SO_SERVICE_URL }?id={match.group(1)}.mp3"
        if query["Category"] and query["Category"] != word["Category"]:
            continue
        words.append(word)
    return next(iter(words), {})


def _to_query(input):
    input = input.split("|")
    index = input[0].strip()
    word = re.sub("\(.*\)", "", index).strip()
    category = input[1].strip() if len(input) > 1 else None
    return dict(Category=category, Index=index, Word=word)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    run(**vars(parser.parse_args()))
