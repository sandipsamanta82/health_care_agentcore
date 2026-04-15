import sqlite3
from typing import List, Dict
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph_checkpoint_aws import AgentCoreMemorySaver
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool

from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode


# 1. Define the State
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], "The conversation history"]


# 2. Define a "Sensitive" Tool
@tool
def send_payment(amount: float, recipient: str):
    """Sends a payment to a recipient."""
    return f"Successfully sent ${amount} to {recipient}"


# 1. Define the SQLite Tool
@tool
def get_claims() -> List[Dict]:
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
tools = [get_claims, send_payment]
tool_node = ToolNode(tools)


# Initialize LLM and bind the tools
llm = ChatBedrockConverse(model="amazon.nova-pro-v1:0")
llm_with_tools = llm.bind_tools(tools)


def call_model(state: AgentState):
    # Prompt instructs the agent to use the tool and format as a table
    system_prompt = "You are a claims assistant. When providing claim summaries, always use Markdown tables."
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# Check if send_payment is being called (for interruption)
def check_sensitive_tool(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "send_payment":
                return "approve_payment"
        return "tools"
    return END


# After tools execute, check if we should continue or end
def should_continue_after_tools(state: AgentState):
    # Check if the last message is a tool message
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        # Check if it's a rejection message
        if "rejected" in last_message.content.lower() or "canceled" in last_message.content.lower():
            return "agent"  # Let agent respond to rejection
        else:
            return END  # Payment successful, end the flow
    return "agent"


# Add a human approval node that just passes through
def human_approval_node(state: AgentState):
    # This node does nothing, just allows for interruption
    return state


# 3. Build the LangGraph Workflow
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.add_node("approve_payment", human_approval_node)


workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", check_sensitive_tool)
workflow.add_edge("approve_payment", "tools")
workflow.add_conditional_edges("tools", should_continue_after_tools)


# 4. Integrate AgentCore Memory
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory, interrupt_before=["approve_payment"])


# --- EXECUTION WITH HUMAN APPROVAL FLOW ---
def run_with_approval():
    """
    Demonstrates the human approval flow for send_payment tool.
    Supports: Approve, Reject, and Edit actions.
    """
    config = {"configurable": {"thread_id": "thread_1"}}
    input_msg = {"messages": [HumanMessage(content="Send $500 to Alice")]}
    
    # Step 1: Initial request - graph will pause at human_approval node
    print("=== STEP 1: Processing initial request ===")
    for event in graph.stream(input_msg, config):
        print(event)
    
    # Step 2: Check current state and display pending tool call
    print("\n=== STEP 2: PAUSED FOR HUMAN APPROVAL ===")
    current_state = graph.get_state(config)
    last_message = current_state.values["messages"][-1]
    
    if not last_message.tool_calls:
        print("No tool calls found. Exiting.")
        return
    
    tool_call = last_message.tool_calls[0]
    print(f"\n⚠️  Pending Tool Call:")
    print(f"   Tool: {tool_call['name']}")
    print(f"   Arguments: {tool_call['args']}")
    print(f"\nOptions:")
    print("  1. approve - Execute the payment as requested")
    print("  2. reject - Cancel the payment")
    print("  3. edit - Modify the payment details")
    
    # Step 3: Get human decision
    print("\n=== STEP 3: Human Decision ===")
    decision = input("Enter your choice (approve/reject/edit): ").strip().lower()
    
    if decision == "approve":
        print("\n✅ Human approved the payment. Proceeding...")
        # Continue execution from the breakpoint - let it run to completion
        for event in graph.stream(None, config, stream_mode="values"):
            if "messages" in event:
                last_msg = event["messages"][-1]
                if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
                    print(f"Message: {last_msg.content[:100]}...")
        print("\n✅ Payment completed successfully!")
        
    elif decision == "reject":
        print("\n❌ Human rejected the payment. Canceling...")
        # Create a tool result message indicating rejection
        tool_result = ToolMessage(
            content="Payment rejected by human approval. The user did not authorize this transaction.",
            tool_call_id=tool_call['id']
        )
        # Update state and mark as completed to avoid going back to agent
        graph.update_state(config, {"messages": [tool_result]}, as_node="tools")
        
        # Get the current state to show the rejection
        final_state = graph.get_state(config)
        print(f"\n❌ Payment canceled. Rejection recorded in conversation history.")
        
    elif decision == "edit":
        print("\n✏️  Edit payment details:")
        new_amount = input("  Enter new amount (or press Enter to keep current): ").strip()
        new_recipient = input("  Enter new recipient (or press Enter to keep current): ").strip()
        
        # Get current values
        current_args = tool_call['args']
        amount = float(new_amount) if new_amount else current_args.get('amount')
        recipient = new_recipient if new_recipient else current_args.get('recipient')
        
        print(f"\n✏️  Modified payment: ${amount} to {recipient}")
        
        # Update the tool call with new values
        last_message.tool_calls[0]['args'] = {'amount': amount, 'recipient': recipient}
        
        # Update the state with the modified message
        graph.update_state(
            config,
            {"messages": [last_message]},
            as_node="approve_payment"
        )
        
        # Continue execution with modified values - stream to completion
        for event in graph.stream(None, config, stream_mode="values"):
            if "messages" in event:
                last_msg = event["messages"][-1]
                if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
                    print(f"Message: {last_msg.content[:100]}...")
        
        print("\n✅ Modified payment completed successfully!")
    
    else:
        print("\n⚠️  Invalid choice. Payment canceled by default.")
        # Create a tool result message indicating invalid choice
        tool_result = ToolMessage(
            content="Payment canceled due to invalid approval choice. The user did not provide a valid response.",
            tool_call_id=tool_call['id']
        )
        graph.update_state(config, {"messages": [tool_result]}, as_node="tools")
        print("\n❌ Payment canceled.")


# Run the approval flow
if __name__ == "__main__":
    run_with_approval()


