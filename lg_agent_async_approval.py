import sqlite3
import json
import uuid
from typing import List, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from typing import Annotated, TypedDict

from approval_manager import ApprovalManager, ApprovalStatus


# 1. Define the State
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], "The conversation history"]


# 2. Define Tools
@tool
def send_payment(amount: float, recipient: str):
    """Sends a payment to a recipient."""
    return f"Successfully sent ${amount} to {recipient}"


@tool
def get_claims() -> List[Dict]:
    """Retrieves all insurance claims from the local SQLite database."""
    conn = sqlite3.connect('agent.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Setup tools
tools = [get_claims, send_payment]
tool_node = ToolNode(tools)

# Initialize LLM
llm = ChatBedrockConverse(model="amazon.nova-pro-v1:0")
llm_with_tools = llm.bind_tools(tools)

# Initialize ApprovalManager
approval_manager = ApprovalManager()


def call_model_node(state: AgentState):
    system_prompt = """You are a helpful payment and claims assistant.

                    When the user asks to send, transfer, or pay money to someone, you MUST use the send_payment tool.
                    Examples that require send_payment:
                    - "Send $500 to Alice"
                    - "Transfer 200 to Bob"
                    - "Pay Charlie 1000 dollars"
                    - "sent 200 to bob"
                    - "I need to send money to David"

                    When providing claim summaries, always use Markdown tables.
                    """
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def human_approval_node(state: AgentState):
    """Pass-through node for interruption"""
    return state


def check_sensitive_tool(state: AgentState):
    """Check if send_payment is being called and save to DB"""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "send_payment":
                # Save to database BEFORE interruption
                # We need to get thread_id from somewhere - for now use a marker
                # The actual thread_id will be set in submit_payment_request
                return "approve_payment"
        return "tools"
    return END


# Conditional edge after tools
def should_continue_after_tools(state: AgentState):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        if "rejected" in last_message.content.lower() or "canceled" in last_message.content.lower():
            return "agent"
        else:
            return END
    return "agent"


# Build the workflow
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model_node)
workflow.add_node("tools", tool_node)
workflow.add_node("approve_payment", human_approval_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", check_sensitive_tool)
workflow.add_edge("approve_payment", "tools")
workflow.add_conditional_edges("tools", should_continue_after_tools)

# Compile graph with SQLite checkpointer for persistence
# This ensures state is saved across program restarts
conn = sqlite3.connect("agent.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
graph = workflow.compile(checkpointer=checkpointer, interrupt_before=["approve_payment"])


# --- STEP 1: Initial Request (saves to DB and pauses) ---
def submit_request(user_message: str, thread_id: str = "thread_1"):
    """Submit a payment request using natural language that will be saved to DB for later approval"""
    config = {"configurable": {"thread_id": thread_id}}
    input_msg = {"messages": [HumanMessage(content=user_message)]}
    
    print(f"=== Submitting Payment Request ===")
    print(f"User Message: {user_message}")
    print(f"Thread ID: {thread_id}\n")
    
    # Stream until interruption
    interrupted = False
    approval_id = None
    
    for event in graph.stream(input_msg, config):
        #print(f"Event: {event}")
        if '__interrupt__' in event:
            interrupted = True
            # Get the current state to extract tool call info
            current_state = graph.get_state(config)
            last_message = current_state.values["messages"][-1]
            
            if last_message.tool_calls:
                tool_call = last_message.tool_calls[0]
                
                # Save to database
                approval_id = approval_manager.save_pending_approval(
                    thread_id=thread_id,
                    tool_name=tool_call['name'],
                    tool_call_id=tool_call['id'],
                    args=tool_call['args']
                )
                
                print(f"\n⚠️  APPROVAL REQUIRED - Saved to database with ID: {approval_id}")
                print(f"   Tool: {tool_call['name']}")
                print(f"   Arguments: {tool_call['args']}")
                print(f"   Use approval CLI to approve/reject/edit this request")
                print(f"\n✓ Request saved to database. Waiting for approval...")
            break
    
    if not interrupted:
        print("\n⚠️  No interruption occurred - Request completed without requiring approval.")
        
        # Get the final state to show the agent's response
        final_state = graph.get_state(config)
        if final_state and hasattr(final_state, 'values') and 'messages' in final_state.values:
            messages = final_state.values['messages']
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, 'content'):
                    print(f"\n📝 Agent Response:")
                    print(f"{last_message.content}")
        
        print("\nThis can happen if:")
        print("  1. The agent didn't call send_payment tool")
        print("  2. The agent called a different tool (like get_claims)")
        print("  3. The agent provided a direct response without using tools")
    
    return thread_id


# --- STEP 2: Process Approval Decision (run later) ---
def process_approval_decision(approval_id: int):
    """Process an approval decision from the database"""
    approval = approval_manager.get_approval_by_id(approval_id)
    
    if not approval:
        print(f"❌ Approval ID {approval_id} not found")
        return
    
    '''
    if approval['status'] != ApprovalStatus.PENDING.value:
        print(f"⚠️  Approval ID {approval_id} already processed with status: {approval['status']}")
        return'''
    
    thread_id = approval['thread_id']
    tool_call_id = approval['tool_call_id']
    config = {"configurable": {"thread_id": thread_id}}
    
    # Get current state
    current_state = graph.get_state(config)
    
    # Check if state exists and has messages
    if not current_state or not hasattr(current_state, 'values') or 'messages' not in current_state.values:
        print(f"❌ No state found for thread_id: {thread_id}")
        print(f"   Make sure the request was submitted with this thread_id")
        return
    
    last_message = current_state.values["messages"][-1]
    
    # Find the tool call
    tool_call = None
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        for tc in last_message.tool_calls:
            if tc['id'] == tool_call_id:
                tool_call = tc
                break
    
    if not tool_call:
        print(f"❌ Tool call {tool_call_id} not found in state")
        print(f"   Last message type: {type(last_message)}")
        print(f"   Has tool_calls: {hasattr(last_message, 'tool_calls')}")
        return
    
    status = approval['status']
    
    if status == ApprovalStatus.APPROVED.value:
        print(f"\n✅ Processing APPROVED request (ID: {approval_id})")
        # Continue execution
        for event in graph.stream(None, config, stream_mode="values"):
            if "messages" in event:
                last_msg = event["messages"][-1]
                if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
                    print(f"Result: {last_msg.content[:100]}...")
        print("✅ Payment completed!")
        
    elif status == ApprovalStatus.REJECTED.value:
        print(f"\n❌ Processing REJECTED request (ID: {approval_id})")
        tool_result = ToolMessage(
            content=f"Payment rejected: {approval.get('rejection_reason', 'No reason provided')}",
            tool_call_id=tool_call_id
        )
        graph.update_state(config, {"messages": [tool_result]}, as_node="tools")
        print("❌ Payment canceled and recorded")
        
    elif status == ApprovalStatus.EDITED.value:
        print(f"\n✏️  Processing EDITED request (ID: {approval_id})")
        modified_args = json.loads(approval['modified_args'])
        print(f"Modified args: {modified_args}")
        
        # Update tool call with new args
        tool_call['args'] = modified_args
        graph.update_state(config, {"messages": [last_message]}, as_node="approve_payment")
        
        # Continue execution
        for event in graph.stream(None, config, stream_mode="values"):
            if "messages" in event:
                last_msg = event["messages"][-1]
                if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
                    print(f"Result: {last_msg.content[:100]}...")
        print("✅ Modified payment completed!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print('  Step 1 - Submit request: python lg_agent_async_approval.py submit "Send $500 to Alice"')
        print("  Step 2 - Process decision: python lg_agent_async_approval.py process <approval_id>")
        print("\nExamples:")
        print('  python lg_agent_async_approval.py submit "Send $500 to Alice"')
        print('  python lg_agent_async_approval.py submit "Transfer 1000 dollars to Bob"')
        print('  python lg_agent_async_approval.py submit "Pay Alice $250"')
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "submit":
        if len(sys.argv) < 3:
            print('Usage: python lg_agent_async_approval.py submit "Your natural language request"')
            print('Example: python lg_agent_async_approval.py submit "Send $500 to Alice"')
            sys.exit(1)
        # Join all remaining arguments as the message
        user_message = " ".join(sys.argv[2:])

        random_id = uuid.uuid4()
        submit_request(user_message, str(random_id))
        
    elif command == "process":
        if len(sys.argv) < 3:
            print("Usage: python lg_agent_async_approval.py process <approval_id>")
            sys.exit(1)
        approval_id = int(sys.argv[2])
        process_approval_decision(approval_id)
        
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: submit, process")

