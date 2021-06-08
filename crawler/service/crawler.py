import datetime
import glob
import multiprocessing
import time
import uuid
from urllib.parse import urlparse, urljoin

import elasticsearch
import requests
from bs4 import BeautifulSoup
import logging
import sys
import random

from elasticsearch.helpers import scan

from website import Website, Link
import traceback
import warnings
from nltk.tokenize import word_tokenize
import nltk
import pandas as pd


from elasticsearch import Elasticsearch


# temp cache locations, data consistency not working yet
link_cache_location = f'/media/td/Samsung_T5/data/dumps/links.csv'
website_cache_location = f'/media/td/Samsung_T5/data/dumps/websites.csv'

warnings.filterwarnings("ignore", message="Unverified HTTPS request is being made to host")

max_links = 5

def get_meta_keywords(soup):
    soup_tag = soup.find('meta', {'name':'keywords'})
    if not soup_tag:
        soup_tag = soup.find('meta', {'name':'og:keywords'})
    if soup_tag and soup_tag.has_attr('content'):
        return soup_tag['content']

def get_meta_description(soup):
    soup_tag = soup.find('meta', {'name':'description'})
    if not soup_tag:
        soup_tag = soup.find('meta', {'name':'og:description'})
    if soup_tag and soup_tag.has_attr('content'):
        return soup_tag['content']


def get_meta_title(soup):
    soup_tag = soup.find('meta', {'name':'title'})
    if not soup_tag:
        soup_tag = soup.find('meta', {'name':'og:title'})
    if soup_tag and soup_tag.has_attr('content'):
        return soup_tag['content']


def clean_text(s):
    if s:
        return ' '.join(word_tokenize(str(s))).replace(',,', ',')

def clean_text_alpha(s):
    if s:
        res = ''
        for i in s:
            if i.lower() <= 'z' and i.lower() >= 'a':
                res+= i
            else:
                res += ' '
        return res


def get_website_id(url):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(url)))


def get_link_id(url1, url2):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(url1) + str(url2)))

def get_record_from_row(row_dict):
    return {k: v for k, v in row_dict.items() if not pd.isnull(v)}


def dump_data():
    es = Elasticsearch()
    query = {
        "query": {
            "match_all": {}
        }
    }

    es.indices.refresh(index="link-index")
    es.indices.refresh(index="website-index")

    links = list()
    websites = list()

    for i in scan(es, index='link-index', query=query):
        links.append(i['_source'])

    for i in scan(es, index='website-index', query=query):
        websites.append(i['_source'])

    df1 = pd.DataFrame.from_dict(links)
    df2 = pd.DataFrame.from_dict(websites)

    print(df1.shape, df2.shape)

    df1.to_csv(link_cache_location, index=False)
    df2.to_csv(f'/media/td/Samsung_T5/data/dumps/websites.csv', index=False)


def load_data():
    es = Elasticsearch()

    df1 = pd.read_csv(link_cache_location)
    df2 = pd.read_csv(f'/media/td/Samsung_T5/data/dumps/websites.csv')

    for n, (idx, row) in enumerate(df1.iterrows()):
        print(n, df1.shape)
        es.index(index="link-index", id=get_link_id(row['source_url'], row['destination_url']), body=get_record_from_row(row.to_dict()))
    for idx, row in df2.iterrows():
        es.index(index="website-index", id=get_website_id(row['url']), body=get_record_from_row(row.to_dict()))

    print('loaded data')



def extract_info_from_website(url, content):
    data = {'url': url}

    data['timestamp'] = datetime.datetime.now().isoformat()

    url_parsed = urlparse(url)
    data['url'] = url_parsed.geturl()
    data['scheme'] = url_parsed.scheme
    data['netloc'] = url_parsed.netloc
    data['params'] = url_parsed.params
    data['query'] = url_parsed.query
    data['fragment'] = url_parsed.fragment

    soup = BeautifulSoup(content, features="html.parser")

    data['meta_kw'] = get_meta_keywords(soup)
    data['meta_title'] = get_meta_title(soup)
    data['meta_description'] = get_meta_description(soup)

    data['content_paragraphs'] = ','.join([i.getText() for i in soup.find_all("p")])
    data['content_headers'] = ','.join([i.getText() for i in soup.find_all(['h1', 'h2', 'h3'])])

    data['meta_kw'] = clean_text(data['meta_kw'])
    data['meta_title'] = clean_text(data['meta_title'])
    data['meta_description'] = clean_text(data['meta_description'])
    data['content_paragraphs'] = clean_text(data['content_paragraphs'])
    data['content_headers'] = clean_text(data['content_headers'])

    links_soup = soup.find_all('a')
    links = list()

    for i in links_soup:
        if i.has_attr('href'):
            link = i['href']

            # check if link is relative
            if not link:
                continue
            if '#' == link[0]:
                continue
            if '/' == link[0]:
                link = url_parsed.scheme + '://' + url_parsed.netloc + link
            parsed_link = urlparse(link)
            if not parsed_link.scheme:
                link = url_parsed.scheme + '://'  + link
            parsed_link = urlparse(link)
            if not parsed_link.scheme:
                continue
            if parsed_link.netloc == url_parsed.netloc:
                continue
            links.append(Link(**{'source_url': url,
                         'timestamp':datetime.datetime.now().isoformat(),
                         'source_url_text_split':clean_text_alpha(url),
                         'link_text':i.getText(),
                         'destination_url':link,
                         'destination_url_text':clean_text_alpha(link)}))

    random.shuffle(links)
    links = links[:max_links]
    return Website(**data), links


class Crawler:
    def __init__(self, tor_port, q_in, q_out):
        self.tor_port = tor_port
        self.q_in = q_in
        self.q_out = q_out
        self.s = requests.session()
        self.es = Elasticsearch()
        print('starting Crawler')

    def run(self):
        while True:
            try:
                url = self.q_in.get()
                if not url:
                    break
                else:
                    website, links = self.scrape_website(url)

                    if website:
                        self.es.index(index="website-index", id=get_website_id(website.url), body=get_record_from_row(website.dict()))

                        for i in links:
                            self.es.index(index="link-index", id=get_link_id(i.source_url, i.destination_url), body=get_record_from_row(i.dict()))

            except Exception as e:
                traceback.print_exc()
                logging.exception(e)
                break


    def scrape_website(self, url):
        try:
            print(f'scraping {url}')

            self.s.headers.update({'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'})
            self.s.proxies = dict(
                http=f"socks5://localhost:{self.tor_port}",
                https=f"socks5://localhost:{self.tor_port}",
            )
            r = self.s.get(url, verify=False, timeout=(60, 60))
            web_data, link_data = extract_info_from_website(url, r.content)
            return web_data, link_data
        except requests.exceptions.ConnectionError:
            print(f'error with this link: {url}')
            time.sleep(5)
        except Exception as e:
            print(f'error with this link: {url}')
            logging.exception(e)
            traceback.print_exc()
            time.sleep(5)
        return None, None



def run_crawler(c_input):
    c = Crawler(**c_input)
    c.run()


def get_urls(keys, max_results: int):
    from elasticsearch.helpers import scan
    results = dict()
    es = Elasticsearch()

    query = {
        "query": {
            "multi_match": {
                "query": " ".join(keys),
                "fields": ["link_text", "destination_url_text"]
            }
        }}
    print('started link query')
    try:
        es.indices.refresh(index="link-index")
        es.indices.refresh(index="website-index")
        for i in scan(es, index = 'link-index', query=query):
            results.setdefault(i['_source']['source_url'], list())
            results[i['_source']['source_url']].append(i['_source']['destination_url'])
            if len(set(results.keys())) >= max_results:
                break
        print(f'ended link query, {len(results)} results found')
    except elasticsearch.exceptions.NotFoundError:
        print('Index not found')
    results_list = list()
    for v in results.values():
        results_list.append(random.choice(v))
    return results_list


def run_crawlers(tor_ports, keys, seed_websites, path, run_size):
    print('starting run_crawlers')
    # db = WebsiteDB(path)
    # q_in = multiprocessing.Queue()
    # q_out = multiprocessing.Queue()
    m = multiprocessing.Manager()
    q_in = m.Queue()
    q_out = m.Queue()
    # links = set()
    # links = db.get_all_links(keys)
    links = get_urls(keys, run_size)
    links = list(seed_websites) + links
    links = list(set(links))
    random.shuffle(links)

    print(len(links))

    links = list(links)[:run_size]

    for i in links:
        q_in.put(i)
    for i in tor_ports:
        q_in.put(None)
    pool_inputs = [{'tor_port':p, 'q_in':q_in, 'q_out':q_out} for p in tor_ports]

    # writer = multiprocessing.Process(target = write_records_p, args = ({'path': path, 'q':q_out, 'attempts': 3},))
    # writer.start()

    crawler_pool = multiprocessing.Pool()
    crawler_pool.map(run_crawler, pool_inputs, chunksize = 1)

    print('pool mapped')
    crawler_pool.close()
    crawler_pool.join()
    print('pool joined')
    # q_out.put({'sentinel': 'sentinel'})
    # writer.join()
    dump_data()


if __name__ == '__main__':
    tor_ports = [9150 + i for i in range(18)]
    keys = [
            'vegan',
    ]

    # load_data()

    seed_websites = [
                        'https://en.wikipedia.org/wiki/Soup',
                     'https://en.wikipedia.org/wiki/List_of_diets',
                     'https://en.wikipedia.org/wiki/Testosterone',
                     'https://en.wikipedia.org/wiki/Muscle_hypertrophy',
                     'https://en.wikipedia.org/wiki/Vietnam',
                     'https://en.wikipedia.org/wiki/Vietnam_War',
                     'https://en.wikipedia.org/wiki/History_of_Vietnam',
                     'http://redditlist.com/',
                     'https://en.wikipedia.org/wiki/List_of_Vietnamese_people',
                     'https://en.wikipedia.org/wiki/Cuisine',
                     'https://en.wikipedia.org/wiki/Tai_languages',
                     'https://en.wikipedia.org/wiki/Vietnamese_people',
                     'https://en.wikipedia.org/wiki/Veganism',
                     'https://en.wikipedia.org/wiki/Vegan_nutrition',
                     'https://en.wikipedia.org/wiki/Vegetarian_cuisine',
                     'https://en.wikipedia.org/wiki/Category:Vegan_cuisine',
                     'https://en.wikipedia.org/wiki/Vegetarianism',
                    ]
    path = '/media/td/Samsung_T5/data/search'
    run_size = 10000
    while True:
        try:
            run_crawlers(tor_ports, keys, seed_websites, path, run_size)
        except:
            traceback.print_exc()
            time.sleep(5)