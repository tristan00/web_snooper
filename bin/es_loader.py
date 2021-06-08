import glob
import datetime
import traceback

import pandas as pd
from elasticsearch import Elasticsearch


es = Elasticsearch()

def get_record_from_row(row_dict):
    return {k: v for k, v in row_dict.items() if not pd.isnull(v)}


es.indices.delete(index="search-index", ignore=[400, 404])
files = glob.glob('/media/td/Samsung_T5/data/search/*/*.csv')
counter = 0
for f in files:
    df = pd.read_csv(f, dtype=str)
    doc = dict()
    for idx, row in df.iterrows():
        counter += 1
        print(counter, row['url'])
        doc = get_record_from_row(row.to_dict())
        try:
            res = es.index(index="search-index", id=str(row['url'])[:256], body=doc)
        except:
            traceback.print_exc()

res = es.get(index="search-index", id=doc['url'])
es.indices.refresh(index="search-index")

res = es.search(index="search-index", body={"query": {"match_all": {}}})
print("Got %d Hits:" % res['hits']['total']['value'])
for hit in res['hits']['hits']:
    print("%(timestamp)s %(author)s: %(text)s" % hit["_source"])