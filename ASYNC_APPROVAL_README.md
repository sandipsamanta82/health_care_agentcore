# Asynchronous Human Approval System

This system allows you to handle payment approvals asynchronously by saving approval requests to a SQLite database. You can submit payment requests at one time and approve/reject/edit them at a later time.

## Architecture

```
┌─────────────────┐
│  Submit Request │ → Saves to DB → Pauses execution
└─────────────────┘
         ↓
┌─────────────────┐
│  Approval CLI   │ → View/Approve/Reject/Edit
└─────────────────┘
         ↓
┌─────────────────┐
│ Process Decision│ → Resumes execution
└─────────────────┘
```

## Components

### 1. **approval_manager.py**
Database manager for approval requests with CRUD operations.

### 2. **aws_agent_async_approval.py**
Main agent with async approval workflow.

### 3. **approval_cli.py**
Command-line interface for managing approval requests.

## Database Schema

```sql
CREATE TABLE approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    tool_call_id TEXT NOT NULL,
    original_args TEXT NOT NULL,
    modified_args TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rejection_reason TEXT,
    UNIQUE(thread_id, tool_call_id)
)
```

## Workflow

### Step 1: Submit Payment Request

Submit a payment request using natural language that will be saved to the database:

```bash
python aws_agent_async_approval.py submit "Send $500 to Alice"
```

**Other examples:**
```bash
python aws_agent_async_approval.py submit "Transfer 1000 dollars to Bob"
python aws_agent_async_approval.py submit "Pay Alice $250"
python aws_agent_async_approval.py submit "I need to send $750 to Charlie"
```

**Output:**
```
=== Submitting Payment Request ===
User Message: Send $500 to Alice
Thread ID: thread_1

⚠️  APPROVAL REQUIRED - Saved to database with ID: 1
   Tool: send_payment
   Arguments: {'amount': 500, 'recipient': 'Alice'}
   Use approval CLI to approve/reject/edit this request

✓ Request saved to database. Waiting for approval...
```

### Step 2: View Pending Approvals

List all pending approval requests:

```bash
python approval_cli.py list
```

**Output:**
```
📋 Pending Approval Requests (1)

+----+---------------+----------+-------------+---------------------+------------+
| ID | Tool          | Amount   | Recipient   | Created At          | Thread ID  |
+====+===============+==========+=============+=====================+============+
|  1 | send_payment  | $500     | Alice       | 2026-04-15 18:00:00 | thread_1   |
+----+---------------+----------+-------------+---------------------+------------+
```

### Step 3: View Approval Details

Get detailed information about a specific approval:

```bash
python approval_cli.py show 1
```

**Output:**
```
📄 Approval Request Details (ID: 1)

Tool Name:       send_payment
Tool Call ID:    tooluse_abc123
Thread ID:       thread_1
Status:          pending
Created At:      2026-04-15 18:00:00
Updated At:      2026-04-15 18:00:00

Original Arguments:
  Amount:        $500
  Recipient:     Alice
```

### Step 4: Make a Decision

#### Option A: Approve

```bash
python approval_cli.py approve 1
```

**Output:**
```
✅ Approved request ID: 1

Next step: Run the following command to process the approval:
  python aws_agent_async_approval.py process 1
```

#### Option B: Reject

```bash
python approval_cli.py reject 1 "Insufficient funds"
```

**Output:**
```
❌ Rejected request ID: 1
   Reason: Insufficient funds

Next step: Run the following command to process the rejection:
  python aws_agent_async_approval.py process 1
```

#### Option C: Edit

```bash
python approval_cli.py edit 1 --amount 300 --recipient Bob
```

**Output:**
```
✏️  Edited request ID: 1
   Original: $500 to Alice
   Modified: $300 to Bob

Next step: Run the following command to process the edited request:
  python aws_agent_async_approval.py process 1
```

### Step 5: Process the Decision

Execute the approved/rejected/edited request:

```bash
python aws_agent_async_approval.py process 1
```

**Output (for approved):**
```
✅ Processing APPROVED request (ID: 1)
Result: Successfully sent $500 to Alice...
✅ Payment completed!
```

**Output (for edited):**
```
✏️  Processing EDITED request (ID: 1)
Modified args: {'amount': 300, 'recipient': 'Bob'}
Result: Successfully sent $300 to Bob...
✅ Modified payment completed!
```

**Output (for rejected):**
```
❌ Processing REJECTED request (ID: 1)
❌ Payment canceled and recorded
```

## CLI Commands Reference

### List Commands

```bash
# List pending approvals
python approval_cli.py list

# List all approvals
python approval_cli.py list-all

# List approvals by status
python approval_cli.py list-all pending
python approval_cli.py list-all approved
python approval_cli.py list-all rejected
python approval_cli.py list-all edited
```

### View Details

```bash
python approval_cli.py show <approval_id>
```

### Approve

```bash
python approval_cli.py approve <approval_id>
```

### Reject

```bash
python approval_cli.py reject <approval_id> <reason>
```

### Edit

```bash
# Edit amount only
python approval_cli.py edit <approval_id> --amount <new_amount>

# Edit recipient only
python approval_cli.py edit <approval_id> --recipient <new_recipient>

# Edit both
python approval_cli.py edit <approval_id> --amount <new_amount> --recipient <new_recipient>
```

## Complete Example Workflow

```bash
# 1. Submit a payment request using natural language
python aws_agent_async_approval.py submit "Send $500 to Alice"
# Output: Saved to database with ID: 1

# 2. Later, view pending requests
python approval_cli.py list
# Shows: ID 1, $500 to Alice

# 3. Decide to edit the amount
python approval_cli.py edit 1 --amount 300
# Output: Modified to $300

# 4. Process the edited request
python aws_agent_async_approval.py process 1
# Output: Successfully sent $300 to Alice
```

## Integration with Your Application

### Submit Request from Your Code

```python
from aws_agent_async_approval import submit_payment_request

# Submit a payment request using natural language
thread_id = submit_payment_request(
    user_message="Send $500 to Alice",
    thread_id="user_session_123"
)

# Or with different phrasings
submit_payment_request("Transfer 1000 dollars to Bob")
submit_payment_request("Pay Charlie $250")
submit_payment_request("I need to send $750 to David")
```

### Process Approval from Your Code

```python
from aws_agent_async_approval import process_approval_decision

# Process an approval decision
process_approval_decision(approval_id=1)
```

### Use ApprovalManager Directly

```python
from approval_manager import ApprovalManager

manager = ApprovalManager()

# Get pending approvals
pending = manager.get_pending_approvals()

# Approve a request
manager.approve_request(approval_id=1)

# Reject a request
manager.reject_request(approval_id=1, reason="Not authorized")

# Edit a request
manager.edit_request(approval_id=1, new_args={"amount": 300, "recipient": "Bob"})
```

## Benefits of Async Approval

1. **Decoupled Workflow**: Submit requests and handle approvals separately
2. **Persistent State**: All approval requests saved in database
3. **Audit Trail**: Complete history of all approvals/rejections/edits
4. **Flexible Timing**: Approve requests hours or days later
5. **Batch Processing**: Review and approve multiple requests at once
6. **Multi-User Support**: Different users can submit and approve requests

## Database Location

By default, approvals are stored in `healthcare.db` in the same directory. You can change this by passing a different path to `ApprovalManager`:

```python
manager = ApprovalManager(db_path="/path/to/your/database.db")
```

## Error Handling

- Attempting to approve/reject/edit a non-pending request will fail gracefully
- Processing a non-existent approval ID will show an error message
- All operations return success/failure status

## Security Considerations

1. **Access Control**: Implement authentication for approval CLI
2. **Audit Logging**: All actions are timestamped in the database
3. **Data Validation**: Validate amounts and recipients before processing
4. **Thread Isolation**: Each thread_id maintains separate conversation state

## Troubleshooting

### Request not found
- Check the approval ID is correct
- Verify the database file exists and is accessible

### Cannot process approval
- Ensure the request status is correct (pending for approve/reject/edit)
- Check that the thread_id matches the original request

### Graph state issues
- Verify the LangGraph checkpointer is properly configured
- Ensure thread_id is consistent between submit and process steps

## Future Enhancements

- Web UI for approval management
- Email notifications for pending approvals
- Approval workflows with multiple approvers
- Time-based auto-rejection
- Approval delegation and escalation
- Integration with external approval systems