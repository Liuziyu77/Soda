import sys
sys.path.append("../")
import torch
import gradio as gr
from mllm.soda_mllm import mllm_openai, mllm_IXC2
from web_search.utils import search, preprocess_search_results, merge_snippet
from web_search.utils import bing_search 
import os
import uuid
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ["GRADIO_TEMP_DIR"] = "./database"
import shutil
import time
import threading
import random
from RAG.utils import preprocess_files, build_text_database
from RAG.utils import build_image_database
from service.utils import rag_database
from sentence_transformers import CrossEncoder
from transformers import AutoModel, AutoTokenizer
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          StoppingCriteria, StoppingCriteriaList)
from transformers.generation import GenerationConfig
from peft import AutoPeftModelForCausalLM

torch.manual_seed(1234)

### globle variable
user_directory = None
image_user_directory = None
txt_collection = None
img_collection = None

### init model
## crose_encoder
cross_encoder_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
## internlm-xcomposer
torch.set_grad_enabled(False)
IXC2_model = AutoModelForCausalLM.from_pretrained('internlm/internlm-xcomposer2-vl-7b', trust_remote_code=True).cuda().eval()
IXC2_tokenizer = AutoTokenizer.from_pretrained('internlm/internlm-xcomposer2-vl-7b', trust_remote_code=True)

"""
set your database path here
"""
base_directory = "/mnt/petrelfs/liuziyu/V3Det/Soda_Dev/web_ui/database/"
# max keep time（s）
max_file_age = 3600  # 1 hour

custom_css = """
body { font-family: 'Arial'; background-color: #f4f4f4; color: #333; }
.header { background-color: #5D1049; padding: 20px; color: #fff; text-align: center; }
.header h1 { margin: 0; }
.button, .tab { background-color: #EAC435; color: #5D1049; border: none; border-radius: 5px; }
.button:hover, .tab:hover { background-color: #F3D70B; }
input, textarea, .textbox {  border-radius: 5px; }
img { border: none; display: block; margin: 0 auto; }
.intro p { color: #333; font-size: 18px; text-align: center; }
# 
"""
# h1 {
#     color: black;
#     font-size: 36px;
#     text-align: center;
# }
# p {
#     color: #555;
#     font-size: 24px;
#     text-align: center;
# }

def clear_old_files():
    while True:
        now = time.time()
        for filename in os.listdir(base_directory):
            file_path = os.path.join(base_directory, filename)
            if os.path.isdir(file_path):
                creation_time = os.path.getctime(file_path)
                if now - creation_time > max_file_age:
                    shutil.rmtree(file_path)
        time.sleep(3600)  # check 1 time per hour
# clear old data
threading.Thread(target=clear_old_files, daemon=True).start()


def web_search_gradio(query, search_engine, mllm, search_num):
    results = search(search_engine, query)
    print(search_engine)
    urls, title, snippet = preprocess_search_results(search_engine, results, search_num)

    ### rerank
    input_cross_encoder = [(query, s) for s in snippet]
    rerank_scores = cross_encoder_model.predict(input_cross_encoder)
    sorted_str_list = [x for _, x in sorted(zip(rerank_scores, snippet), reverse=True)]

    web_contents_combined = merge_snippet(sorted_str_list)

    if mllm == "GPT4-V":
        answer = mllm_openai(query, web_contents_combined)
    elif mllm =="InternLM-Xcomposer2":
        answer = mllm_IXC2(IXC2_model, IXC2_tokenizer, query, web_contents_combined)
    links = []
    for i in range(len(urls)):
        links.append((title[i], urls[i]))
    links = "\n".join([f"[{title}]({url})" for title, url in links])
    return links, answer

def process_uploaded_text_file(file_upload):
    global user_directory
    global txt_collection

    try:
        session_id = f"{int(time.time())}_{random.randint(0, 1000)}"
        user_directory = os.path.join(base_directory, session_id)
        os.makedirs(user_directory, exist_ok=True)
        target_path = os.path.join(user_directory, file_upload.name.split("/")[-1])
        shutil.move(file_upload.name, target_path)

        docs = preprocess_files(file_path = target_path,chunk_size=500, chunk_overlap=50)
        txt_collection = build_text_database(docs, batch_size=40000, encoder="intfloat/multilingual-e5-base", database_name = session_id, database_path = user_directory+"_database")
        return "Database has been built."
    except Exception as e:
        print("Error:", e)
        return "Database built error"

def text_rag_gradio(query, n_results, mllm):
    global txt_collection
    try:
        ans = txt_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        ans = ans["documents"][0]

        ### rerank 
        input_cross_encoder = [(query, s) for s in ans]
        rerank_scores = cross_encoder_model.predict(input_cross_encoder)
        sorted_str_list = [x for _, x in sorted(zip(rerank_scores, ans), reverse=True)]

        ans_combined = merge_snippet(sorted_str_list)
        if mllm == "GPT4-V":
            answer = mllm_openai(query, ans_combined)
        elif mllm =="InternLM-Xcomposer2":
            answer = mllm_IXC2(IXC2_model, IXC2_tokenizer, query, ans_combined)
        return ans_combined,answer
    except Exception as e:
        print(f"RAG database error: {e}")
        return f"{e}"


def process_uploaded_image_fold_file(images_upload):
    global img_collection
    global image_user_directory
    file_paths = [file.name for file in images_upload]
    session_id = f"{int(time.time())}_{random.randint(0, 1000)}"
    image_user_directory = os.path.join(base_directory, session_id)
    os.makedirs(image_user_directory, exist_ok=True)

    for file_path in file_paths:
        target_path = os.path.join(image_user_directory, file_path.split("/")[-1])
        shutil.move(file_path, target_path)
    
    img_collection = build_image_database(fold_path = image_user_directory, database_name = session_id, database_path = image_user_directory+"_database")

    return "Database has been built."

def image_rag_gradio(image_upload):
    test_image_path = image_upload.name
    n_pictures = 4
    ans = img_collection.query(
            query_uris=[test_image_path], # A list of strings representing URIs to data
            n_results=n_pictures
        )
    retrieved_image_path = []
    retrieved_image_path.append(image_user_directory+"/"+ans["metadatas"][0][0]["ID"]+'.jpg')
    retrieved_image_path.append(image_user_directory+"/"+ans["metadatas"][0][1]["ID"]+'.jpg')
    retrieved_image_path.append(image_user_directory+"/"+ans["metadatas"][0][2]["ID"]+'.jpg')
    return [test_image_path],retrieved_image_path


"""
Gradio main function
"""
def main():
    # SimplyRetrieve App
    with gr.Blocks(title="SODA Agent",css=custom_css) as app:
        gr.Markdown("""
        <div class="intro">
        <p>
        </p>
        </div>
        """)
        with gr.Row():
            gr.Markdown("")
            gr.Image(value="./soda_title.png",  show_download_button=False,
                     container=False)
            gr.Markdown("")

        gr.Markdown("""

        <div class="intro">
        <p>
        🚀🚀🚀Welcome to the SODA: <strong>Search, Organize, Discover Anything</strong>. This multi-functional tool helps you search the web, process text and images, and leverage large language models to derive insights. 🚀🚀🚀
        </p>
        </div>

        Choose a tab to begin using specific functionalities:

        🌐 **Web Search**: Search the internet using your preferred search engine.

        🔎 **Text Retrieve**: Upload and process text files, and ask questions based on their content.

        🌅 **Image Retrieve**: Manage and retrieve images based on uploaded content.


        Link to our Github: [SODA](https://github.com/Liuziyu77/Soda)
        """)

        with gr.Tab("Web Search"):
            with gr.Row():
                # Input section - where users can type their query
                web_search_query = gr.Textbox(label="Enter your query here", placeholder="Type your query...", lines=2)
                search_engine_dropdown = gr.Dropdown(label="Select Search Engine", choices=["google", "bing"],
                                                     value="bing")
                web_mllm_dropdown = gr.Dropdown(label="Select mllms", choices=["GPT4-V", "InternLM-Xcomposer2"],
                                                     value="GPT4-V")
                search_num_slider = gr.Slider(label="Number of results", minimum=0, maximum=10, step=1, value=10)
                web_search_button = gr.Button("Search")

            with gr.Row():
                # Output section - divided into two parts: search results and LLM response
                with gr.Column(scale=1):
                    web_search_results = gr.Textbox(label="Web Search Results", placeholder="Search results from web will appear here...", lines=10, interactive=False)
                with gr.Column(scale=1):
                    web_search_answer = gr.Textbox(label="LLM Response", placeholder="LLM's response will appear here...", lines=10, interactive=False)

        with gr.Tab("Text Retrieve"):
            with gr.Row():
                with gr.Column(scale=1):
                    text_file_upload = gr.components.File(label="Upload a file or folder")
                    text_file_upload_status = gr.Textbox(label="Database status:", placeholder="No database...")
                    process_text_file_button = gr.Button("Process File")
                    with gr.Row():
                        text_mllm_dropdown = gr.Dropdown(label="Select mllms", choices=["GPT4-V", "InternLM-Xcomposer2"],
                                                        value="GPT4-V")                      
                        text_rag_n_results_slider = gr.Slider(label="Number of Retrieved Texts", minimum=1, maximum=10,step=1, value=3)
                with gr.Column(scale=1):
                    text_question_input = gr.Textbox(label="Enter your question", placeholder="Type your question here...", lines=2)
                    text_rag_button = gr.Button("Submit Question")
            with gr.Row():
                # Display section for search results and answer
                with gr.Column(scale=1):
                    text_rag_results = gr.Textbox(label="Local Database Search Results", placeholder="Search results from local database will appear here...", lines=10, interactive=False)
                with gr.Column(scale=1):
                    text_rag_answer = gr.Textbox(label="LLM Response", placeholder="LLM's response will appear here....", lines=10, interactive=False)

        with gr.Tab("Image Retrieve"):
            with gr.Row():
                with gr.Column(scale=1):
                    image_file_input = gr.components.File(label="Upload a file or folder", file_count="multiple")
                    image_file_input_status = gr.Textbox(label="Database status:", placeholder="No database...")
                    process_image_file_button = gr.Button("Process Images")
                with gr.Column(scale=1):
                    image_question_upload = gr.components.File(label="Upload a single image for retrieval")
                    image_rag_button = gr.Button("Retrieve Images")
            with gr.Row():
                with gr.Column(scale=1):
                    origin_images = gr.Gallery(label="Original Images", show_label=True, columns=[3], rows=[1], object_fit="contain", height="auto")
                with gr.Column(scale=1):
                    retrieved_images = gr.Gallery(label="Retrieved Images", show_label=True, columns=[3], rows=[1], object_fit="contain", height="auto")

        # Web Search Event
        web_search_button.click(
            fn=web_search_gradio,
            inputs=[web_search_query, search_engine_dropdown, web_mllm_dropdown, search_num_slider],
            outputs=[web_search_results, web_search_answer]
        )
        # Text RAG Event
        process_text_file_button.click(process_uploaded_text_file, inputs = text_file_upload, outputs = text_file_upload_status)
        text_rag_button.click(
            fn=text_rag_gradio,
            inputs=[text_question_input, text_rag_n_results_slider, text_mllm_dropdown],
            outputs=[text_rag_results, text_rag_answer]
        )
        # Image RAG Event
        process_image_file_button.click(process_uploaded_image_fold_file, inputs = image_file_input, outputs = image_file_input_status)
        image_rag_button.click(image_rag_gradio, inputs=image_question_upload, outputs=[origin_images,retrieved_images])

    # App Main Settings
    app.queue(max_size=100)
    app.launch(share=True, server_name="0.0.0.0", server_port=10078)

if __name__ == "__main__":
    main()
