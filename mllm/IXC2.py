import clip
import json
import torch
import numpy as np
from PIL import Image
from tqdm import tqdm
Image.MAX_IMAGE_PIXELS = None
import matplotlib.pyplot as plt
from sentence_transformers import CrossEncoder
from transformers import AutoModel, AutoTokenizer
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          StoppingCriteria, StoppingCriteriaList)
from transformers.generation import GenerationConfig
from peft import AutoPeftModelForCausalLM

torch.manual_seed(1234)

torch.set_grad_enabled(False)
model = AutoModelForCausalLM.from_pretrained('internlm/internlm-xcomposer2-vl-7b', trust_remote_code=True).cuda().eval()
tokenizer = AutoTokenizer.from_pretrained('internlm/internlm-xcomposer2-vl-7b', trust_remote_code=True)


query = '<ImageHere>'+ "What do you see in the picture?"
with torch.no_grad():
    query = query
    image = "./test_img.jpg"
    with torch.cuda.amp.autocast():
        response, _ = model.chat(tokenizer, query=query, image=image, history=[], do_sample=False)
    print("\033[92m" + response + "\033[0m")