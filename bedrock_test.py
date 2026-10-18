import os
import boto3

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")

client = boto3.client("bedrock-runtime", region_name="us-east-1")

response = client.converse(
    modelId=MODEL_ID,
    messages=[
        {
            "role": "user",
            "content": [
                {"text": "Write a two-sentence friendly follow-up email to Priya about a pricing proposal."}
            ],
        }
    ],
    inferenceConfig={"maxTokens": 200, "temperature": 0.5},
)

print(response["output"]["message"]["content"][0]["text"])  