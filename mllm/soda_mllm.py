from openai import OpenAI
import torch

# Enter your OpenAI API here:
api_base = "***********************************"
api_key = "***********************************"

# call gpt4v
def mllm_openai(query, search_results):  
    conversation_history = []
    client = OpenAI(api_key=api_key, base_url=api_base)
    response = client.chat.completions.create(
      model="gpt-4-0125-preview",
      messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": f"Given a input text and web information, please response to the input text with these information.\n Here is the input text: {query}.\n Here is the materials: {search_results}"},
      ]
    )
    # print(response.choices[0].message.content)
    return response.choices[0].message.content

# call InternLM-Xcomposer2
def mllm_IXC2(IXC2_model, IXC2_tokenizer, query, search_results):  
  text_inputs = f"Given a input text and web information, please response to the input text with these information.\n Here is the input text: {query}.\n Here is the materials: {search_results}"
  with torch.no_grad():
      query = text_inputs
      with torch.cuda.amp.autocast():
          response, _ = IXC2_model.chat(IXC2_tokenizer, query=text_inputs, history=[], do_sample=False)
      # print("\033[92m" + response + "\033[0m")
      return response