import sqlite3
from typing import List, Dict
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph_checkpoint_aws import AgentCoreMemorySaver
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool

# 1. Define the SQLite Tool
@tool
def get_claims_data() -> List[Dict]:
    """Retrieves all insurance claims from the local SQLite database."""
    conn = sqlite3.connect('healthcare.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims")
    rows = cursor.fetchall()
    conn.close()
    # Convert rows to a list of dicts for the LLM
    return [dict(row) for row in rows]

# 2. Setup the Graph with Tool Binding
tools = [get_claims_data]
tool_node = ToolNode(tools)

# Initialize LLM and bind the tools
llm = ChatBedrockConverse(model="amazon.nova-pro-v1:0")
llm_with_tools = llm.bind_tools(tools)

def call_model(state: MessagesState):
    # Prompt instructs the agent to use the tool and format as a table
    system_prompt = "You are a claims assistant. When providing claim summaries, always use Markdown tables."
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# 3. Build the LangGraph Workflow
workflow = StateGraph(MessagesState)
workflow.add_node("claim_agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "claim_agent")
# Conditional edge: If the model calls a tool, go to 'tools', otherwise end
def should_continue(state: MessagesState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow.add_conditional_edges("claim_agent", should_continue)
workflow.add_edge("tools", "claim_agent")

# 4. Integrate AgentCore Memory
MEMORY_ID = "memory_health_care-X4a6sqEP1E"
checkpointer = AgentCoreMemorySaver(MEMORY_ID, region_name="us-east-1")
graph = workflow.compile(checkpointer=checkpointer)

# 5. AgentCore Deployment Entrypoint
app = BedrockAgentCoreApp()

@app.entrypoint
def handle_agent_request(payload, context):
    user_input = payload.get("input", "")
    config = {
        "configurable": {
            "thread_id": getattr(context, "session_id", "default_thread"),
            "actor_id": getattr(context, "actor_id", "default_user")
        }
    }
    
    result = graph.invoke({"messages": [("user", user_input)]}, config=config)
    return {"output": result["messages"][-1].content}

if __name__ == "__main__":
    app.run()