import sys
sys.path.append("../")
from mllm.soda_mllm import mllm_openai
from web_search.utils import search, preprocess_search_results, merge_snippet, get_web_contents

### input snippet to LLM
async def web_search_snippet(query, search_engine='google', search_num=10, search_type=None):
    try:
        results = search(search_engine, query)
        urls, title, snippet = preprocess_search_results(search_engine, results, search_num, search_type)
        web_contents_combined = merge_snippet(snippet)
        answer = mllm_openai(query,web_contents_combined)
        return answer
    except Exception as e:
        print(f"Web search error: {e}")

### input whole web page to LLM
async def web_search_pagehtml(query, search_engine='google', search_num=3, search_type=None):
    try:
        results = search(search_engine, query)
        urls, title, snippet = preprocess_search_results(search_engine, results, search_num, search_type)
        web_contents = await get_web_contents(urls)
        print(len((web_contents)))
        web_contents_combined = " ".join(web_contents)
        answer = mllm_openai(query,web_contents_combined)
        return answer
    except Exception as e:
        print(f"Web search error: {e}")

### retrieve database
def rag_database(query, text_num, text_collection):
    try:
        ans = text_collection.query(
            query_texts=[query],
            n_results=text_num
        )
        ans = ans["documents"][0]
        ans_combined = merge_snippet(ans)
        print("RAG text:")
        print(ans_combined)
        answer = mllm_openai(query,ans_combined)
        return answer
    except Exception as e:
        print(f"RAG database error: {e}")