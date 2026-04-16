import boto3
import json

# 1. Initialize the client
client = boto3.client('bedrock-agentcore', region_name="us-east-1")

# 2. Define the payload
# Use the 'prompt' key as defined in your @app.entrypoint logic
payload = {
    "prompt": "Show me a summary of all active claims in a table."
}

# 3. Call the agent
# session_id persists memory (at least 33 characters recommended)
response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/your-agent-id",
    runtimeSessionId="unique-uuid-per-conversation-session",
    payload=json.dumps(payload).encode('utf-8')
)

# 4. Handle the streaming or JSON response
if response.get("contentType") == "application/json":
    response_body = json.loads(response['response'].read())
    print("Agent Response:\n", response_body.get("output"))
else:
    # If streaming is enabled, iterate through the chunks
    for event in response['response']:
        chunk = event.decode('utf-8')
        print(chunk, end="")
