import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote
from lxml import etree
from functools import lru_cache
from cps.services.Metadata import Metadata
import gzip
from datetime import datetime
import re,json
from urllib.request import Request, urlopen
import urllib.parse

PROVIDER_ID = "novel_id"
PROVIDER_NAME = "JJWXC Novels"
JJWXC_NOVEL_URL = 'http://www.jjwxc.net/onebook.php?novelid=%s'
JJWXC_NOVEL_API = 'https://app.jjwxc.net/androidapi/novelbasicinfo?novelId=%s'

class JJWXC(Metadata):
    __name__ = PROVIDER_NAME
    __id__ = PROVIDER_ID

    def __init__(self):
        self.searcher = JjwxcNovelSearcher(5)
        super().__init__()

    def search(self, query, generic_cover=""):
        if self.active:
            return self.searcher.search_novels(query)


class JjwxcNovelSearcher:
    def __init__(self, max_workers):
        self.novel_loader = NovelLoader()
        self.max_workers = max_workers
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='douban_async')
    def load_novel_urls(self,query,search_pages):
        key_title,key_author=query.split(";")[0],query.split(";")[1]
        key_author="".join(key_author)
        encode_keywork = urllib.parse.quote(key_title.encode('gbk'))
        find_dict={}
        for page in range(1,search_pages):
            search_url="http://www.jjwxc.net/search.php?kw=%s&t=1&p=%d&ord=novelscore"%(encode_keywork,page)
            try:
                res = urlopen((Request(search_url,headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'})))
                res_utf=res.read()
                ress = etree.HTML(res_utf)
                for i in range(2,27):
                    book_name=ress.xpath("//*[@id='search_result']//div[%d]/h3/a//text()"%i)
                    book_url=ress.xpath("//*[@id='search_result']//div[%d]/h3/a/@href"%i)
                    author=ress.xpath("//*[@id='search_result']//div[%d]/div[2]/a/span/text()"%i)
                    book_name = "".join(book_name).replace(" ","").replace("\n","").replace("\r","")
                    book_url = "".join(book_url).replace(" ","").replace("\n","").replace("\r","")
                    author = "".join(author).replace(" ","").replace("\n","").replace("\r","")
                    if len(book_url.split("id=")[-1])!=0:
                        if len(key_author)==0 :
                            find_dict[book_name]=book_url
                        elif key_author in author :
                                find_dict[book_name+"-"+author]=book_url
            except:
                pass
        urls=[]
        for i in find_dict.values():
            urls.append(JJWXC_NOVEL_API%i.split("id=")[-1])
        return urls
    
    def search_novels(self, query):
        novel_urls = self.load_novel_urls(query,10)
        novels = []
        futures = [self.thread_pool.submit(self.novel_loader.load_novel, novel_url) for novel_url in novel_urls]
        for future in as_completed(futures):
            novel = future.result()
            if novel is not None:
                novels.append(future.result())
        return novels


class NovelLoader:
    def __init__(self):
        self.novel_parser = JJWXC_NOVEL_Parser()

    def load_novel(self, novel_url):
        novel = None
        start_time = time.time()
        res = urlopen(Request(novel_url,headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'}))
        if res.status in [200, 201]:
            novel = self.novel_parser.parse_novel(novel_url)            
            print("下载书籍:{}成功,耗时{:.0f}ms".format(novel_url, (time.time() - start_time) * 1000))
        return novel


class JJWXC_NOVEL_Parser:
    def __init__(self):
        aa="aa"
    def parse_novel(self, novel_url):
        res=urlopen(Request(novel_url,headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'}))
        res=res.read()
        res_dict = json.loads(res)
        intro = ""
        novel_id="".join(res_dict["novelId"])
        try:
            intro_ = res_dict["novelIntro"].replace("&lt;","").replace("&gt;","").split("br/")
            for i,j in enumerate(intro_):
                if (j != ""):
                    intro+=j+"\n"
        except:
            pass
        try:
            res2 = urlopen(Request(JJWXC_NOVEL_URL%novel_id,headers={'Accept-Encoding': 'gzip, deflate','user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'}))
            res2=res2.read()
            res2=gzip.decompress(res2).decode("gbk").encode("utf-8").decode("utf-8")
            res2=etree.HTML(res2)
            pubdate=res2.xpath("//*[@id='oneboolt']/tbody//td[6]/@title")
            pubdate="".join(pubdate)
            pubdate=pubdate.split("\n")[-1].split(" ")[0].split("：")[-1].rstrip("\n")
        except:
            pubdate=""
        novel={}
        novel['url'] = JJWXC_NOVEL_URL%novel_id
        novel['title'] = "".join(res_dict["novelName"])
        novel['id']=novel_id
        novel['publisher'] = "晋江文学城"
        novel['authors'] = []
        authors="".join(res_dict["authorName"])
        novel['authors'].append(authors)
        novel['cover'] = "".join(res_dict["novelCover"])
        novel['description'] = intro
        novel['tags'] = res_dict["novelTags"].split(",")
        novel['rating']=""
        try:
            novel['rating']= float(res_dict["novelReviewScore"].split("分")[0]) / 2.0
        except:
            novel['rating']=""
        novel['publishedDate']= str(pubdate)
        novel['source'] = {
            "id": PROVIDER_ID,
            "description": PROVIDER_NAME,
            "link": "http://www.jjwxc.net/"
        }
        return novel
