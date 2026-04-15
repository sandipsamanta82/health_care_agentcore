"""
Test script to demonstrate the human approval flow for send_payment tool.
This script shows how the approval mechanism works with approve/reject/edit options.
"""

from aws_agent_core import graph
from langchain_core.messages import HumanMessage

def test_approval_flow():
    """
    Test the human approval flow with different scenarios.
    """
    print("=" * 60)
    print("HUMAN APPROVAL FLOW TEST")
    print("=" * 60)
    
    config = {"configurable": {"thread_id": "thread_1"}}
    
    # Test Case 1: Request a payment
    print("\n📝 Test Case: Requesting payment of $500 to Alice")
    print("-" * 60)
    
    input_msg = {"messages": [HumanMessage(content="Send $500 to Alice")]}
    
    # Step 1: Stream initial request (will pause at human_approval)
    print("\n🔄 Processing request...")
    for event in graph.stream(input_msg, config):
        for node_name, node_output in event.items():
            print(f"  Node: {node_name}")
            if "messages" in node_output:
                last_msg = node_output["messages"][-1]
                if hasattr(last_msg, 'content') and last_msg.content:
                    print(f"  Content: {last_msg.content[:100]}...")
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    print(f"  Tool Calls: {last_msg.tool_calls}")
    
    # Step 2: Check state
    print("\n⏸️  PAUSED - Waiting for human approval")
    current_state = graph.get_state(config)
    last_message = current_state.values["messages"][-1]
    
    if last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        print(f"\n⚠️  Pending Tool Call:")
        print(f"   Tool: {tool_call['name']}")
        print(f"   Arguments: {tool_call['args']}")
        print(f"\n   Next State: {current_state.next}")
        
        print("\n" + "=" * 60)
        print("HUMAN DECISION OPTIONS:")
        print("=" * 60)
        print("1. Type 'approve' - Execute payment as requested")
        print("2. Type 'reject' - Cancel the payment")
        print("3. Type 'edit' - Modify payment details")
        print("=" * 60)
        
        # Get user input
        decision = input("\nEnter your choice (approve/reject/edit): ").strip().lower()
        
        if decision == "approve":
            print("\n✅ APPROVED - Executing payment...")
            for event in graph.stream(None, config):
                for node_name, node_output in event.items():
                    print(f"  Node: {node_name}")
                    if "messages" in node_output:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  Result: {last_msg.content}")
            print("\n✅ Payment completed successfully!")
            
        elif decision == "reject":
            print("\n❌ REJECTED - Canceling payment...")
            last_message.tool_calls = []
            graph.update_state(config, {"messages": [HumanMessage(content="Payment was rejected by human approval.")]})
            for event in graph.stream(None, config):
                for node_name, node_output in event.items():
                    print(f"  Node: {node_name}")
                    if "messages" in node_output:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  Response: {last_msg.content}")
            print("\n❌ Payment canceled.")
            
        elif decision == "edit":
            print("\n✏️  EDIT MODE - Modify payment details")
            new_amount = input("  Enter new amount (or press Enter to keep $500): ").strip()
            new_recipient = input("  Enter new recipient (or press Enter to keep 'Alice'): ").strip()
            
            current_args = tool_call['args']
            amount = float(new_amount) if new_amount else current_args.get('amount')
            recipient = new_recipient if new_recipient else current_args.get('recipient')
            
            print(f"\n✏️  Modified payment: ${amount} to {recipient}")
            
            last_message.tool_calls[0]['args'] = {'amount': amount, 'recipient': recipient}
            graph.update_state(config, {"messages": [last_message]})
            
            print("\n🔄 Executing modified payment...")
            for event in graph.stream(None, config):
                for node_name, node_output in event.items():
                    print(f"  Node: {node_name}")
                    if "messages" in node_output:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  Result: {last_msg.content}")
            print("\n✅ Modified payment completed successfully!")
        
        else:
            print("\n⚠️  Invalid choice. Payment canceled by default.")
            last_message.tool_calls = []
            graph.update_state(config, {"messages": [HumanMessage(content="Invalid approval choice. Payment canceled.")]})
            for event in graph.stream(None, config):
                pass
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


def approve_request():
    """
    Test the human approval flow with different scenarios.
    """
    print("=" * 60)
    print("HUMAN APPROVAL FLOW TEST")
    print("=" * 60)
    
    config = {"configurable": {"thread_id": "thread_1"}}    
    
    # Step 2: Check state
    print("\n⏸️  PAUSED - Waiting for human approval")
    current_state = graph.get_state(config)
    print(current_state)
    
    last_message = current_state.values["messages"][-1]
    
    if last_message.tool_calls:
        tool_call = last_message.tool_calls[0]
        print(f"\n⚠️  Pending Tool Call:")
        print(f"   Tool: {tool_call['name']}")
        print(f"   Arguments: {tool_call['args']}")
        print(f"\n   Next State: {current_state.next}")
        
        print("\n" + "=" * 60)
        print("HUMAN DECISION OPTIONS:")
        print("=" * 60)
        print("1. Type 'approve' - Execute payment as requested")
        print("2. Type 'reject' - Cancel the payment")
        print("3. Type 'edit' - Modify payment details")
        print("=" * 60)
        
        # Get user input
        decision = input("\nEnter your choice (approve/reject/edit): ").strip().lower()
        
        if decision == "approve":
            print("\n✅ APPROVED - Executing payment...")
            for event in graph.stream(None, config):
                for node_name, node_output in event.items():
                    print(f"  Node: {node_name}")
                    if "messages" in node_output:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  Result: {last_msg.content}")
            print("\n✅ Payment completed successfully!")
            
        elif decision == "reject":
            print("\n❌ REJECTED - Canceling payment...")
            last_message.tool_calls = []
            graph.update_state(config, {"messages": [HumanMessage(content="Payment was rejected by human approval.")]})
            for event in graph.stream(None, config):
                for node_name, node_output in event.items():
                    print(f"  Node: {node_name}")
                    if "messages" in node_output:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  Response: {last_msg.content}")
            print("\n❌ Payment canceled.")
            
        elif decision == "edit":
            print("\n✏️  EDIT MODE - Modify payment details")
            new_amount = input("  Enter new amount (or press Enter to keep $500): ").strip()
            new_recipient = input("  Enter new recipient (or press Enter to keep 'Alice'): ").strip()
            
            current_args = tool_call['args']
            amount = float(new_amount) if new_amount else current_args.get('amount')
            recipient = new_recipient if new_recipient else current_args.get('recipient')
            
            print(f"\n✏️  Modified payment: ${amount} to {recipient}")
            
            last_message.tool_calls[0]['args'] = {'amount': amount, 'recipient': recipient}
            graph.update_state(config, {"messages": [last_message]})
            
            print("\n🔄 Executing modified payment...")
            for event in graph.stream(None, config):
                for node_name, node_output in event.items():
                    print(f"  Node: {node_name}")
                    if "messages" in node_output:
                        last_msg = node_output["messages"][-1]
                        if hasattr(last_msg, 'content'):
                            print(f"  Result: {last_msg.content}")
            print("\n✅ Modified payment completed successfully!")
        
        else:
            print("\n⚠️  Invalid choice. Payment canceled by default.")
            last_message.tool_calls = []
            graph.update_state(config, {"messages": [HumanMessage(content="Invalid approval choice. Payment canceled.")]})
            for event in graph.stream(None, config):
                pass
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    #test_approval_flow()
    approve_request()

# Made with Bob
