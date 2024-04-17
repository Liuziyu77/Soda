import re
import json
import urllib
import urllib.request
import requests
import html2text
import urllib.request
from IPython.display import HTML
import asyncio
import aiohttp

"""
Input your search engine API here
"""
def google_search(query):
    try:
        api_key = '********************************'
        cx = '****************************'
        url = 'https://www.googleapis.com/customsearch/v1'
        params = {'key': api_key, 'cx': cx, 'q': query}
        response = requests.get(url, params=params)
        data = response.json()
        ### ["link"], ["title"], ["snippet"]
        return data['items']
    except Exception as e:
        print(f"Google API Search Failed: {e}")
        raise e

"""
Input your search engine API here
"""
def bing_search(query):
    try:
        subscription_key = "*****************************"
        assert subscription_key
        search_url = "https://api.bing.microsoft.com/v7.0/search"
        
        search_term = query
    
        headers = {"Ocp-Apim-Subscription-Key": subscription_key}
        params = {"q": search_term, "textDecorations": True, "textFormat": "HTML"}
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()
    
        ### ["url"], ["name"], ["snippet"]
        return search_results["webPages"]["value"]
    except Exception as e:
        print(f"Bing API Search Failed: {e}")
        raise e

"""
Input your search engine API here
"""
def serper_search(query, search_type):
    try:
        url = f"https://google.serper.dev/{search_type}"
        payload = json.dumps({
          "q": query,
          "num": 10
        })
        headers = {
          'X-API-KEY': '**********************************',
          'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        search_results = json.loads(response.text)
    
        if search_type == "images":
            ### ["link"], ["title"], ["imageUrl"]
            return search_results["images"]
            
        elif search_type == "videos":
            ### ["link"], ["title"], ["snippet"], ["imageUrl"]
            return search_results["videos"]
    except Exception as e:
        print(f"Serper API Search Failed: {e}")
        raise e

"""
Web search
"""
def search(search_engine, query, search_type=None):
    if search_engine == "google":
        search_results = google_search(query)
        return search_results
    elif search_engine == "bing":
        search_results = bing_search(query)
        return search_results
    elif search_engine == "serper":
        search_results = serper_search(query, search_type)
        return search_results
    else:
        print("Search engine is not support.")

def preprocess_search_results(search_engine, search_results, search_num=5, search_type=None):
    if search_engine == "google":
        url = []
        title = []
        snippet = []
        for item in search_results:
            url.append(item["link"])
            title.append(item["title"])
            snippet.append(item["snippet"])
        if len(search_results)>=search_num:
            return url[:search_num], title[:search_num], snippet[:search_num]
        else:
            return url, title, snippet
        
    elif search_engine == "bing":
        url = []
        title = []
        snippet = []
        for item in search_results:
            url.append(item["url"])
            title.append(item["name"])
            snippet.append(item["snippet"])
        if len(search_results)>=search_num:
            return url[:search_num], title[:search_num], snippet[:search_num]
        else:
            return url, title, snippet
            
    elif search_engine == "serper":
        url = []
        title = []
        image_url = []
        snippet = []
        if search_type=="images":
            for item in search_results:
                url.append(item["link"])
                title.append(item["title"])
                image_url.append(item["imageUrl"])
            if len(search_results)>=search_num:
                return url[:search_num], title[:search_num], image_url[:search_num]
            else:
                return url, title, image_url
            
        elif search_type == "videos":
            for item in search_results:
                url.append(item["link"])
                title.append(item["title"])
                image_url.append(item["imageUrl"])
                snippet.append(item["snippet"])
            if len(search_results)>=search_num:
                return url[:search_num], title[:search_num], image_url[:search_num], snippet[:search_num]
            else:
                return url, title, image_url, snippet
    else:
        print("Search engine is not support.")

"""
抓取页面方法，调用该方法返回抓取到数据
"""
async def get_web_contents(urls):
    try:
        async with aiohttp.ClientSession(trust_env = True) as session:
            # tasks = [get_web_content(session, url) for url in urls]
            tasks = [read_pageHtml(session, url) for url in urls]
            web_contents = await asyncio.gather(*tasks, return_exceptions=False)
            return web_contents
    except aiohttp.ClientResponseError as e:
        print(f"get web contents failed: {e}")
        return []

async def read_pageHtml(session, url):
    async with session.get(url) as response:
        try:  
            response.raise_for_status()
            print(response)
            try:
                response.encoding = 'utf-8'
                html = await response.text()
            except UnicodeDecodeError:
                try:
                    response.encoding = 'gbk'
                    html = await response.text()
                except Exception as e:
                    print(f"An error occurred during decode html: {e}")

            # HTML(html)
            h = html2text.HTML2Text()
            h.ignore_links = True
            h.ignore_images = True
            page_string = h.handle(html)
            page_string = page_string.replace("\n","")
            return page_string
        
        except Exception as e:
            print(f"An error occurred during read web pages: {e}")
            return None

def read_single_pageHtml(url):
    try:
        file = urllib.request.urlopen(url)
        data = file.read()
        # decode to string
        try:
            decoded_html = data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                decoded_html = data.decode('gbk')
            except Exception as e:
                print(f"An error occurred during decode html: {e}")

        # string to html
        HTML(decoded_html)
        # html to markdown
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        page_string = h.handle(decoded_html)
        page_string = page_string.replace("\n","")
        return page_string
    
    except Exception as e:
        print(f"An error occurred during read web pages: {e}")
        return None

def merge_snippet(str_list):
    numbered_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(str_list))
    return numbered_str

"""
rerank
"""