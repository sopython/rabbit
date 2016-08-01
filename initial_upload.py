from itertools import islice
import xml.etree.ElementTree as ET
from elasticsearch import Elasticsearch
from dateutil.parser import parse as parse_date
import html
import re
from bs4 import BeautifulSoup
from io import BytesIO
from tokenize import tokenize, NAME

es = Elasticsearch()

def tokenize_code(code):
    soup = BeautifulSoup(code, 'html.parser')
    var_names = set()
    for code_block in soup.find_all('code'):
        try:
            for ttype, tval, *rest in tokenize(BytesIO(code_block.text.encode('utf-8')).readline):
                if ttype == NAME:
                    var_names.add(tval)
        except Exception:
            pass

    return list(var_names)



context = ET.iterparse('/mnt/sopython-db/Posts.xml')
context = iter(context)
event, root = next(context)
inserted = 0
for idx, (event, elem) in islice(enumerate(context), 1000000):
    if idx % 1000 == 0:
        print(idx, 'processed and', inserted, 'inserted')
    if event == 'end' and elem.tag == 'row':
        post_type = elem.get('PostTypeId')
        post_id = int(elem.get('Id'))
        for k, v in elem.attrib.items():
            if k.endswith(('Id', 'Count')):
                elem.attrib[k] = int(v)
            elif k.endswith('Date'):
                elem.attrib[k] = parse_date(v)

        if post_type == '1' and elem.get('LastActivityDate').year >= 2015:
            tags = re.findall('<(.*?)>', html.unescape(elem.get('Tags')))
            elem.attrib['Tags'] = tags
            if any('python' in tag for tag in tags):
                elem.attrib['code_names'] = tokenize_code(elem.get('Body'))
                es.index(index='python', doc_type='q', id=post_id, body=elem.attrib)
                inserted += 1
    elem.clear()
    root.clear()


