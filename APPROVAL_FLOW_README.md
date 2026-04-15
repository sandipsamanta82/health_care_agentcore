# Human Approval Flow for send_payment Tool

This implementation provides a human-in-the-loop approval mechanism for the `send_payment` tool, allowing humans to **approve**, **reject**, or **edit** payment requests before execution.

## Overview

The system uses LangGraph's interruption mechanism to pause execution when the `send_payment` tool is about to be called, giving humans the opportunity to review and control the action.

## Key Features

✅ **Selective Interruption**: Only `send_payment` tool calls trigger interruption; `get_claims` executes normally  
✅ **Three Action Options**: Approve, Reject, or Edit payment details  
✅ **State Management**: Uses LangGraph checkpointer to maintain conversation state  
✅ **Flexible Editing**: Modify amount and/or recipient before execution  

## Architecture

### Graph Structure

```
START → agent → [check_sensitive_tool] → human_approval → tools → agent → END
                                      ↓
                                    tools (for get_claims)
```

### Key Components

1. **`check_sensitive_tool()`** - Conditional edge function that routes:
   - `send_payment` calls → `human_approval` node (triggers interruption)
   - `get_claims` calls → `tools` node (no interruption)
   - No tool calls → `END`

2. **`human_approval` node** - Pass-through node that serves as the interruption point

3. **`interrupt_before=["human_approval"]`** - Graph compilation parameter that pauses execution

## Usage

### Running the Approval Flow

```python
# Run the main script
python aws_agent_core.py

# Or run the test script
python test_approval_flow.py
```

### Approval Flow Steps

1. **Request Initiated**: User requests a payment (e.g., "Send $500 to Alice")

2. **Graph Pauses**: Execution stops at `human_approval` node

3. **Review Pending Action**: System displays:
   ```
   ⚠️  Pending Tool Call:
      Tool: send_payment
      Arguments: {'amount': 500.0, 'recipient': 'Alice'}
   ```

4. **Human Decision**: Choose one of three options:

   **Option 1: Approve**
   ```
   Enter your choice: approve
   ✅ Payment executed as requested
   ```

   **Option 2: Reject**
   ```
   Enter your choice: reject
   ❌ Payment canceled, agent notified of rejection
   ```

   **Option 3: Edit**
   ```
   Enter your choice: edit
   Enter new amount: 750
   Enter new recipient: Bob
   ✏️  Modified payment: $750 to Bob
   ✅ Modified payment executed
   ```

## Code Examples

### Basic Approval Flow

```python
from aws_agent_core import graph
from langchain_core.messages import HumanMessage

config = {"configurable": {"thread_id": "thread_1"}}
input_msg = {"messages": [HumanMessage(content="Send $500 to Alice")]}

# Step 1: Initial request (pauses at human_approval)
for event in graph.stream(input_msg, config):
    print(event)

# Step 2: Get current state
current_state = graph.get_state(config)
last_message = current_state.values["messages"][-1]
tool_call = last_message.tool_calls[0]

# Step 3: Human decision
decision = input("Enter choice (approve/reject/edit): ")

if decision == "approve":
    # Continue execution
    for event in graph.stream(None, config):
        print(event)
```

### Rejecting a Payment

```python
# After graph pauses...
last_message.tool_calls = []
graph.update_state(config, {
    "messages": [HumanMessage(content="Payment rejected by human.")]
})

# Resume to get agent's response
for event in graph.stream(None, config):
    print(event)
```

### Editing Payment Details

```python
# After graph pauses...
tool_call = last_message.tool_calls[0]

# Modify the arguments
tool_call['args'] = {
    'amount': 750.0,
    'recipient': 'Bob'
}

# Update state with modified tool call
graph.update_state(config, {"messages": [last_message]})

# Resume execution with new values
for event in graph.stream(None, config):
    print(event)
```

## Implementation Details

### File: `aws_agent_core.py`

**Key Functions:**

- **`check_sensitive_tool(state)`** (lines 71-78)
  - Inspects tool calls in the last message
  - Routes `send_payment` to `human_approval` node
  - Routes other tools directly to `tools` node

- **`human_approval_node(state)`** (lines 82-84)
  - Pass-through node that enables interruption
  - Returns state unchanged

- **`run_with_approval()`** (lines 127-195)
  - Demonstrates complete approval workflow
  - Handles approve/reject/edit logic
  - Shows state management patterns

### Graph Compilation

```python
graph = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_approval"]
)
```

The `interrupt_before` parameter tells LangGraph to pause execution before entering the `human_approval` node.

## Testing

### Test Non-Sensitive Tool (get_claims)

```python
input_msg = {"messages": [HumanMessage(content="Show me all claims")]}
for event in graph.stream(input_msg, config):
    print(event)
# Executes immediately without interruption
```

### Test Sensitive Tool (send_payment)

```python
input_msg = {"messages": [HumanMessage(content="Send $500 to Alice")]}
for event in graph.stream(input_msg, config):
    print(event)
# Pauses for human approval
```

## State Management

The system uses LangGraph's checkpointer to maintain state across interruptions:

```python
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory, interrupt_before=["human_approval"])
```

Each conversation thread is identified by `thread_id`:

```python
config = {"configurable": {"thread_id": "unique_thread_id"}}
```

## Error Handling

- **Invalid Choice**: Defaults to rejection if invalid input provided
- **No Tool Calls**: Gracefully exits if no tool calls found
- **Empty Input**: Keeps original values when editing

## Integration with AWS Agent Core

The commented section (lines 197-216) shows how to integrate with AWS Bedrock Agent Core:

```python
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
```

## Best Practices

1. **Always check for tool calls** before accessing them
2. **Use unique thread IDs** for each conversation
3. **Validate user input** before modifying tool arguments
4. **Log approval decisions** for audit trails
5. **Handle edge cases** (empty inputs, invalid amounts, etc.)

## Future Enhancements

- Add approval timeout mechanism
- Implement approval history logging
- Support multiple approvers
- Add approval reason/notes field
- Create web UI for approval interface
- Add notification system for pending approvals

## Troubleshooting

**Issue**: Graph doesn't pause  
**Solution**: Ensure `interrupt_before=["human_approval"]` is set and node name matches exactly

**Issue**: Tool executes without approval  
**Solution**: Verify `check_sensitive_tool()` routes `send_payment` to `human_approval` node

**Issue**: State not persisting  
**Solution**: Ensure checkpointer is configured and thread_id is consistent

## License

This implementation is part of the healthcare AWS agent core project.