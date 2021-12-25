import argparse
import bs4
import pandas as pd
import re
import requests


def run(input, output):
    url = 'http://folkets-lexikon.csc.kth.se/folkets/service'
    words = []
    for word in pd.read_csv(input, names=['word'])['word']:
        print('Word: {}'.format(word))
        response = requests.get(url, params=dict(word=word))
        print('  Response: {}'.format(response.status_code))
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        key, word = None, {}
        for element in soup.find('p').children:
            if element.name == 'a':
                if element.get('title') == 'Ladda ner uttalet':
                    word['Audio'] = element['href']
                    continue
            if element.name == 'b' and key:
                word[key] = word.get(key, [])
                word[key].append(element.text.replace('|', ''))
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
                match = re.match('\s*(.*),\s*', element.text)
                if match:
                    word['Category'] = match.group(1)
                    continue
            if not key:
                match = re.match('Uttal:\s*(\[.*\])\s*', element.text)
                if match:
                    word['Pronunciation'] = match.group(1)
                    continue
        print('  Content: {}'.format(word))
        words.append(word)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    run(**vars(parser.parse_args()))
