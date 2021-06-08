import elasticsearch
import pandas as pd
from elasticsearch import Elasticsearch

from elasticsearch.helpers import scan



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

    df1.to_csv(f'/media/td/Samsung_T5/data/dumps/links.csv', index=False)
    df2.to_csv(f'/media/td/Samsung_T5/data/dumps/websites.csv', index=False)


def load_data():
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

    df1.to_csv(f'/media/td/Samsung_T5/data/dumps/links.csv', index=False)
    df2.to_csv(f'/media/td/Samsung_T5/data/dumps/websites.csv', index=False)


dump_data()