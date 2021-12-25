import argparse
import bs4
import json
import pandas as pd
import re
import requests
import shutil

from pathlib import Path

_COLUMNS = [
    'Swedish', 'English', 'Definition', 'Category', 'Pronunciation', 'Audio'
]
_FL_URL = 'http://folkets-lexikon.csc.kth.se/folkets/service'
_SO_URL = 'https://svenska.se/so'
_SO_SERVICE_URL = 'https://isolve-so-service.appspot.com/pronounce'


def run(input, output):
    words = []
    queries = pd.read_csv(input, names=['Query'])['Query']
    for query in queries:
        print('Slår upp ordet {}...'.format(query))
        word = {**_read_so(query), **_read_fl(query)}
        print(json.dumps(word, ensure_ascii=False, indent=2))
        words.append(word)
    words = pd.DataFrame(data=words, columns=_COLUMNS, index=queries)
    words['Category'].fillna('okänd', inplace=True)
    for category in sorted(words['Category'].unique()):
        path = Path(output) / category
        path.mkdir(parents=True, exist_ok=True)
        chunk = words[words['Category'] == category]
        chunk.index.to_series().to_csv(path / '_index.csv', index=False)
        chunk[_COLUMNS[:-1]].to_csv(path / '_import.csv', index=False)
        for query, word in chunk[~chunk['Audio'].isnull()].iterrows():
            print('Laddar ner ljudet {}...'.format(query))
            with requests.get(word['Audio'], stream=True) as response:
                with open(path / (query + '.mp3'), 'wb') as file:
                    shutil.copyfileobj(response.raw, file)


def _read_fl(query):
    word = {}
    response = requests.get(_FL_URL, params=dict(word=query))
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    element, key = soup.find('p'), None
    for element in (element.children if element else []):
        if element.name == 'a':
            if element.get('title') == 'Ladda ner uttalet':
                word['Audio'] = element['href']
                continue
        if element.name == 'b' and key:
            value = element.text.replace('|', '')
            word[key] = word[key] + ', ' + value if key in word else value
            continue
        if element.name == 'br':
            key = None
            continue
        if element.name == 'img':
            if element['alt'] == '(Svenska)':
                key = 'Swedish'
                continue
            if element['alt'] == '(Engelska)':
                key = 'English'
                continue
        if key and not 'Category' in word:
            match = re.match('\s*(\w+).*', element.text)
            if match:
                word['Category'] = match.group(1)
                continue
        if not key:
            match = re.match('Uttal:\s*(\[.*\])\s*', element.text)
            if match:
                word['Pronunciation'] = match.group(1)
                continue
    return word


def _read_so(query):
    word = {}
    response = requests.get(_SO_URL,
                            params=dict(sok=query),
                            headers={'User-Agent': 'curl/7.77.0'})
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    element = soup.find('div', {'class': 'lemmalista'})
    if not element:
        return word
    element_ = element.find('div', {'class': 'ordklass'})
    if element_:
        word['Category'] = element_.text
    element_ = element.find('span', {'class': 'def'})
    if element_:
        word['Definition'] = element_.text.replace('\n', '')
    element_ = element.find('a', {'class': 'ljudfil'})
    if element_:
        match = re.match("playAudioForLemma\('(.+)'\);", element_['onclick'])
        if match:
            word['Audio'] = \
                _SO_SERVICE_URL + '?id={}.mp3'.format(match.group(1))
    return word


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    run(**vars(parser.parse_args()))
