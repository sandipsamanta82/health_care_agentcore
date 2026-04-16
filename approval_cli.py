#!/usr/bin/env python3
"""
CLI tool for managing payment approval requests
"""
import sys
import json
from approval_manager import ApprovalManager, ApprovalStatus
from tabulate import tabulate


def list_pending_approvals(manager: ApprovalManager):
    """List all pending approval requests"""
    pending = manager.get_pending_approvals()
    
    if not pending:
        print("✓ No pending approval requests")
        return
    
    print(f"\n📋 Pending Approval Requests ({len(pending)})\n")
    
    table_data = []
    for approval in pending:
        args = json.loads(approval['original_args'])
        table_data.append([
            approval['id'],
            approval['tool_name'],
            f"${args.get('amount', 'N/A')}",
            args.get('recipient', 'N/A'),
            approval['created_at'],
            approval['thread_id']
        ])
    
    headers = ["ID", "Tool", "Amount", "Recipient", "Created At", "Thread ID"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()


def list_all_approvals(manager: ApprovalManager, status: str = None):
    """List all approval requests with optional status filter"""
    approvals = manager.list_all_approvals(status)
    print(approvals)
    
    '''
    if not approvals:
        print(f"✓ No approval requests{' with status: ' + status if status else ''}")
        return
    
    print(f"\n📋 Approval Requests ({len(approvals)}){' - Status: ' + status if status else ''}\n")
    
    table_data = []
    for approval in approvals:
        args = json.loads(approval['original_args'])
        modified = json.loads(approval['modified_args']) if approval['modified_args'] else None
        
        amount_display = f"${args.get('amount', 'N/A')}"
        if modified:
            amount_display = f"${args.get('amount')} → ${modified.get('amount')}"
        
        recipient_display = args.get('recipient', 'N/A')
        if modified:
            recipient_display = f"{args.get('recipient')} → {modified.get('recipient')}"
        
        status_emoji = {
            'pending': '⏳',
            'approved': '✅',
            'rejected': '❌',
            'edited': '✏️'
        }.get(approval['status'], '❓')
        
        table_data.append([
            approval['id'],
            approval['thread_id'],
            approval['tool_name'],
            amount_display,
            recipient_display,
            #f"{status_emoji} {approval['status']}",
            approval['status'],
            approval['updated_at']
        ])
    
    headers = ["ID", "Thread ID", "Tool", "Amount", "Recipient", "Status", "Updated At"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()'''


def show_approval_details(manager: ApprovalManager, approval_id: int):
    """Show detailed information about an approval request"""
    approval = manager.get_approval_by_id(approval_id)
    
    if not approval:
        print(f"❌ Approval ID {approval_id} not found")
        return
    
    args = json.loads(approval['original_args'])
    modified = json.loads(approval['modified_args']) if approval['modified_args'] else None
    
    print(f"\n📄 Approval Request Details (ID: {approval_id})\n")
    print(f"Tool Name:       {approval['tool_name']}")
    print(f"Tool Call ID:    {approval['tool_call_id']}")
    print(f"Thread ID:       {approval['thread_id']}")
    print(f"Status:          {approval['status']}")
    print(f"Created At:      {approval['created_at']}")
    print(f"Updated At:      {approval['updated_at']}")
    print(f"\nOriginal Arguments:")
    print(f"  Amount:        ${args.get('amount', 'N/A')}")
    print(f"  Recipient:     {args.get('recipient', 'N/A')}")
    
    if modified:
        print(f"\nModified Arguments:")
        print(f"  Amount:        ${modified.get('amount', 'N/A')}")
        print(f"  Recipient:     {modified.get('recipient', 'N/A')}")
    
    if approval['rejection_reason']:
        print(f"\nRejection Reason: {approval['rejection_reason']}")
    
    print()


def approve_request(manager: ApprovalManager, approval_id: int):
    """Approve a pending request"""
    if manager.approve_request(approval_id):
        print(f"✅ Approved request ID: {approval_id}")
        print(f"\nNext step: Run the following command to process the approval:")
        print(f"  python aws_agent_async_approval.py process {approval_id}")
    else:
        print(f"❌ Failed to approve request ID: {approval_id}")
        print("   (Request may not exist or is not in pending status)")


def reject_request(manager: ApprovalManager, approval_id: int, reason: str):
    """Reject a pending request"""
    if manager.reject_request(approval_id, reason):
        print(f"❌ Rejected request ID: {approval_id}")
        print(f"   Reason: {reason}")
        print(f"\nNext step: Run the following command to process the rejection:")
        print(f"  python aws_agent_async_approval.py process {approval_id}")
    else:
        print(f"❌ Failed to reject request ID: {approval_id}")
        print("   (Request may not exist or is not in pending status)")


def edit_request(manager: ApprovalManager, approval_id: int, amount: float = None, recipient: str = None):
    """Edit a pending request"""
    approval = manager.get_approval_by_id(approval_id)
    
    if not approval:
        print(f"❌ Approval ID {approval_id} not found")
        return
    
    if approval['status'] != ApprovalStatus.PENDING.value:
        print(f"❌ Cannot edit request ID {approval_id} - status is {approval['status']}")
        return
    
    # Get original args
    original_args = json.loads(approval['original_args'])
    
    # Build new args
    new_args = {
        'amount': amount if amount is not None else original_args.get('amount'),
        'recipient': recipient if recipient is not None else original_args.get('recipient')
    }
    
    if manager.edit_request(approval_id, new_args):
        print(f"✏️  Edited request ID: {approval_id}")
        print(f"   Original: ${original_args.get('amount')} to {original_args.get('recipient')}")
        print(f"   Modified: ${new_args['amount']} to {new_args['recipient']}")
        print(f"\nNext step: Run the following command to process the edited request:")
        print(f"  python aws_agent_async_approval.py process {approval_id}")
    else:
        print(f"❌ Failed to edit request ID: {approval_id}")


def main():
    manager = ApprovalManager()
    
    if len(sys.argv) < 2:
        print("Payment Approval CLI")
        print("\nUsage:")
        print("  List pending:     python approval_cli.py list")
        print("  List all:         python approval_cli.py list-all [status]")
        print("  Show details:     python approval_cli.py show <id>")
        print("  Approve:          python approval_cli.py approve <id>")
        print("  Reject:           python approval_cli.py reject <id> <reason>")
        print("  Edit:             python approval_cli.py edit <id> [--amount <amount>] [--recipient <recipient>]")
        print("\nStatuses: pending, approved, rejected, edited")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        list_pending_approvals(manager)
        
    elif command == "list-all":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        list_all_approvals(manager, status)
        
    elif command == "show":
        if len(sys.argv) < 3:
            print("Usage: python approval_cli.py show <id>")
            sys.exit(1)
        approval_id = int(sys.argv[2])
        show_approval_details(manager, approval_id)
        
    elif command == "approve":
        if len(sys.argv) < 3:
            print("Usage: python approval_cli.py approve <id>")
            sys.exit(1)
        approval_id = int(sys.argv[2])
        approve_request(manager, approval_id)
        
    elif command == "reject":
        if len(sys.argv) < 4:
            print("Usage: python approval_cli.py reject <id> <reason>")
            sys.exit(1)
        approval_id = int(sys.argv[2])
        reason = " ".join(sys.argv[3:])
        reject_request(manager, approval_id, reason)
        
    elif command == "edit":
        if len(sys.argv) < 3:
            print("Usage: python approval_cli.py edit <id> [--amount <amount>] [--recipient <recipient>]")
            sys.exit(1)
        
        approval_id = int(sys.argv[2])
        amount = None
        recipient = None
        
        # Parse optional arguments
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--amount" and i + 1 < len(sys.argv):
                amount = float(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--recipient" and i + 1 < len(sys.argv):
                recipient = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        
        if amount is None and recipient is None:
            print("❌ Must specify at least --amount or --recipient")
            sys.exit(1)
        
        edit_request(manager, approval_id, amount, recipient)
        
    else:
        print(f"Unknown command: {command}")
        print("Valid commands: list, list-all, show, approve, reject, edit")
        sys.exit(1)


if __name__ == "__main__":
    main()

