import os
import glob
import shutil
import logging
import chromadb
import numpy as np
import pandas as pd
import sentence_transformers
from chromadb.utils import embedding_functions
from chromadb.utils.data_loaders import ImageLoader
from langchain.document_loaders import PyMuPDFLoader
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from langchain.text_splitter import RecursiveCharacterTextSplitter, TokenTextSplitter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("initial")

"""
Load Files Function
"""
### return file format
def identify_file_type(file_path):
    _, file_extension = os.path.splitext(file_path)
    file_extension = file_extension.lower()

    if file_extension == '.pdf':
        return 'PDF'
    elif file_extension == '.txt':
        return 'Text'
    elif file_extension == '.tsv':
        return 'TSV'
    elif file_extension == '.csv':
        return 'CSV'
    else:
        return None

### load PDF，TXT，DOCX
def documents_load_local(doc_path):
    try:
        docs = []
        docs.extend(PyMuPDFLoader(doc_path).load())
        return docs
    except Exception as e:
        print(f"Documentes loaded failed: {e}")
        raise e

### load PDF
def documents_load_pdf(pdf_path):
    loader = PyPDFLoader(pdf_path)
    docs = loader.load_and_split()
    return docs

### load CVS
def documents_load_csv(path):
    docs = pd.read_csv(path, sep='\t', header=None)
    return docs

"""
Preprocess loaded text files
"""
### split documents for different chunk_size
def documents_split(docs,chunk_size, chunk_overlap):
    try:
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        # text_splitter =  TokenTextSplitter(encoding_name=encoder, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        docs_split = text_splitter.split_documents(docs)
        return docs_split
    except Exception as e:
        print(f"Documentes split failed: {e}")
        raise e

def documents_to_str(docs):
    docs_str = []
    for doc in docs:
        docs_str.append(doc.dict()["page_content"])
    return docs_str


def preprocess_files(file_path, chunk_size, chunk_overlap):
    docs = documents_load_local(file_path)
    docs_split =  documents_split(docs, chunk_size, chunk_overlap)
    docs_split[0].dict()["page_content"]
    docs_split_str = documents_to_str(docs_split)
    return docs_split_str

"""
Build text database
"""
def build_text_database(docs, batch_size, encoder="intfloat/multilingual-e5-base", database_name = "test", database_path = "./database/test"):
    if os.path.exists(database_path):
        print(f"Database '{database_name}' exists. Change a new name.")
        return None
    else:
        ### text encoder
        embeddings = HuggingFaceEmbeddings(model_name=encoder, encode_kwargs={'normalize_embeddings': True})
        ### client
        client = chromadb.PersistentClient(path=database_path)
        ### text encoder funtino 
        text_emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=encoder, normalize_embeddings = True)
    
        ### create collection
        txt_collection = client.create_collection(name=database_name, embedding_function=text_emb_fn, metadata={"hnsw:space": "cosine"})
    
        ### load collection
        txt_collection = client.get_collection(name=database_name, embedding_function=text_emb_fn)

        for start_idx in range(0, len(docs), batch_size):
            end_idx = min(start_idx + batch_size, len(docs))
            batch_docs = docs[start_idx:end_idx]
            ids = [str(num) for num in range(start_idx, end_idx)]
            # embeddings
            logging.info("Begin embedding docs.")
            embed_split = embeddings.embed_documents(batch_docs)
            logging.info("End embedding docs.")

            # add to database
            metadatas = [{"ID": num} for num in ids]
            logging.info("Begin adding documents.")
            txt_collection.add(
                documents=batch_docs,
                embeddings=embed_split,
                ids=ids,
            )
            logging.info(f"Batch {start_idx // batch_size + 1} done!")
        logging.info("All done!")
    
        return txt_collection


### delete database
def delete_folder(folder_path):
    # check the fold
    if os.path.exists(folder_path):
        # delete the fold
        shutil.rmtree(folder_path)
        print(f"Folder '{folder_path}' has been deleted.")
    else:
        print(f"Folder '{folder_path}' does not exist.")


"""
Read fold with images
"""
def read_image_files(folder_path):
    # format
    image_formats = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.tiff"]
    image_paths = []
    for format in image_formats:
        image_paths.extend(glob.glob(os.path.join(folder_path, format)))
    
    return image_paths



"""
Build image database
"""
def build_image_database(fold_path, database_name = "test", database_path = "./database/test"):
    
    ### client
    client = chromadb.PersistentClient(path=database_path)
    ### image encoder function 
    img_emb_fn = OpenCLIPEmbeddingFunction()
    ### data loader
    data_loader = ImageLoader()
    ### creat collection
    img_collection = client.create_collection(name=database_name, embedding_function=img_emb_fn, metadata={"hnsw:space": "cosine"})
    ### load collection
    img_collection = client.get_collection(name=database_name, embedding_function=img_emb_fn, data_loader=data_loader)

    image_paths = [os.path.join(fold_path, file) for file in os.listdir(fold_path) if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
    print("total image number is: "+str(len(image_paths)))
    ids = list(range(0, len(image_paths)))
    ids = [str(num) for num in ids]
    image_names = [os.path.splitext(os.path.basename(url))[0] for url in image_paths]
    metadatas = [{"ID":metadata} for metadata in image_names]
    logging.info("Begin building database")
    img_collection.add(
        ids=ids, 
        uris = image_paths, 
        metadatas=metadatas,
    )
    logging.info("Done!")

    return img_collection


"""
Build multimodal database
"""
def build_multimodal_database(tsv_path, image_folder, encoder="intfloat/multilingual-e5-base", database_name = "test"):
    ### text encoder
    embeddings = HuggingFaceEmbeddings(model_name=encoder, encode_kwargs={'normalize_embeddings': True})
    ### client
    client = chromadb.PersistentClient(path=f"./database/{database_name}")
    ### text/image encoder function 
    text_emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-base")
    img_emb_fn = OpenCLIPEmbeddingFunction()
    ### data loader
    data_loader = ImageLoader()
    
    
    txt_collection = client.create_collection(name=f"{database_name}_text", embedding_function=text_emb_fn, metadata={"hnsw:space": "cosine"})
    img_collection = client.create_collection(name=f"{database_name}_image", embedding_function=img_emb_fn, metadata={"hnsw:space": "cosine"})
    
    ### load collection
    txt_collection = client.get_collection(name=f"{database_name}_text", embedding_function=text_emb_fn)
    img_collection = client.get_collection(name=f"{database_name}_image", embedding_function=img_emb_fn, data_loader=data_loader)
    
    
    ### add data
    ### embed_text [[float],[float],[float],...]; docs_split [str,str,str,...]
    df = pd.read_csv(tsv_path, sep='\t')
    
    docs_split = df["INFO"]
    docs_split = [s for s in docs_split]
    
    metadatas = df["PATH"]
    metadatas = [s for s in metadatas]
    image_paths = metadatas.copy()
    metadatas = [{"ID":metadata} for metadata in metadatas]

    ids = list(range(0, len(docs_split)))
    ids = [str(num) for num in ids]

    logging.info("Len of data is: "+str(len(ids)))

    
    logging.info("Begin add text.")
    txt_collection.add(
        documents = docs_split,
        ids = ids,
        metadatas = metadatas
    )
    logging.info("End add text.")

    image_paths = [image_folder+image_path for image_path in image_paths]
    logging.info("Begin add images.")
    img_collection.add(
        ids=ids, 
        uris = image_paths, 
        metadatas=metadatas 
    )
    logging.info("End add images.")
    logging.info("ALL DONE!")

    return txt_collection, img_collection