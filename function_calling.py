from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import Demo.checkVulnVersions as dm

model_id = "mistralai/Mistral-7B-Instruct-v0.3"
tokenizer = AutoTokenizer.from_pretrained(model_id)
conversation = [{"role": "user", "content": "Check which versions are vulnerable in Demo/VersionInfo.txt"}]

tools = [
    dm.readVersionInfo,
    dm.checkVulnVersion,
    dm.updateToLatestVersion,
    dm.retrieveLatestVersion
         ]


inputs = tokenizer.apply_chat_template(
            conversation,
            tools=tools,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
)

model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.bfloat16, device_map="auto")

inputs.to(model.device)
outputs = model.generate(**inputs, max_new_tokens=1000)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))

