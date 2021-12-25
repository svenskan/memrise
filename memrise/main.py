import argparse
import bs4
import json
import pandas as pd
import re
import requests

_FL_URL = 'http://folkets-lexikon.csc.kth.se/folkets/service'
_SO_URL = 'https://svenska.se/so'
_SO_SERVICE_URL = 'https://isolve-so-service.appspot.com/pronounce'


def run(input, output):
    words = []
    queries = pd.read_csv(input, names=['query'])['query']
    for query in queries:
        print(query)
        word = {**_read_so(query), **_read_fl(query)}
        print(json.dumps(word, ensure_ascii=False, indent=2))
        words.append(word)
    words = pd.DataFrame(words, index=queries)
    words = words[ \
        ['Swedish', 'English', 'Definition', 'Category', 'Pronunciation']
    ]
    words.to_csv(output)


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
        if key == 'Swedish':
            match = re.match('\s*(.+),\s*', element.text)
            if match:
                value = match.group(1).split(' ')[0]
                if value:
                    word['Category'] = value
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
    element_ = element.find('div', {'class': 'ordklass'}) if element else None
    if element_:
        word['Category'] = element_.text
    element_ = element.find('span', {'class': 'def'}) if element else None
    if element_:
        word['Definition'] = element_.text.replace('\n', '')
    element_ = element.find('a', {'class': 'ljudfil'}) if element else None
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
