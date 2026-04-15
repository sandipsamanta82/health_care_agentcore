import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class ApprovalManager:
    """Manages human approval requests in SQLite database"""
    
    def __init__(self, db_path: str = "healthcare.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the approvals table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
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
        """)
        conn.commit()
        conn.close()
    
    def save_pending_approval(
        self, 
        thread_id: str, 
        tool_name: str, 
        tool_call_id: str, 
        args: Dict
    ) -> int:
        """Save a pending approval request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO approvals (thread_id, tool_name, tool_call_id, original_args, status)
            VALUES (?, ?, ?, ?, ?)
        """, (thread_id, tool_name, tool_call_id, json.dumps(args), ApprovalStatus.PENDING.value))
        
        approval_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return approval_id
    
    def get_pending_approvals(self, thread_id: Optional[str] = None) -> List[Dict]:
        """Get all pending approval requests, optionally filtered by thread_id"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if thread_id:
            cursor.execute("""
                SELECT * FROM approvals 
                WHERE status = ? AND thread_id = ?
                ORDER BY created_at DESC
            """, (ApprovalStatus.PENDING.value, thread_id))
        else:
            cursor.execute("""
                SELECT * FROM approvals 
                WHERE status = ?
                ORDER BY created_at DESC
            """, (ApprovalStatus.PENDING.value,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_approval_by_id(self, approval_id: int) -> Optional[Dict]:
        """Get a specific approval request by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def approve_request(self, approval_id: int) -> bool:
        """Approve a pending request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE approvals 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = ?
        """, (ApprovalStatus.APPROVED.value, approval_id, ApprovalStatus.PENDING.value))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def reject_request(self, approval_id: int, reason: str = "Rejected by user") -> bool:
        """Reject a pending request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE approvals 
            SET status = ?, rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = ?
        """, (ApprovalStatus.REJECTED.value, reason, approval_id, ApprovalStatus.PENDING.value))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def edit_request(self, approval_id: int, new_args: Dict) -> bool:
        """Edit a pending request with new arguments"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE approvals 
            SET status = ?, modified_args = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = ?
        """, (ApprovalStatus.EDITED.value, json.dumps(new_args), approval_id, ApprovalStatus.PENDING.value))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def get_approval_status(self, thread_id: str, tool_call_id: str) -> Optional[Dict]:
        """Get the status of a specific approval request"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM approvals 
            WHERE thread_id = ? AND tool_call_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        """, (thread_id, tool_call_id))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def list_all_approvals(self, status: Optional[str] = None) -> List[Dict]:
        """List all approval requests, optionally filtered by status"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT * FROM approvals 
                WHERE status = ?
                ORDER BY created_at DESC
            """, (status,))
        else:
            cursor.execute("""
                SELECT * FROM approvals 
                ORDER BY created_at DESC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_approval(self, approval_id: int) -> bool:
        """Delete an approval request"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM approvals WHERE id = ?", (approval_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success


if __name__ == "__main__":
    # Test the ApprovalManager
    manager = ApprovalManager()
    
    # Create a test approval
    approval_id = manager.save_pending_approval(
        thread_id="test_thread_1",
        tool_name="send_payment",
        tool_call_id="test_call_123",
        args={"amount": 500, "recipient": "Alice"}
    )
    print(f"Created approval request with ID: {approval_id}")
    
    # List pending approvals
    pending = manager.get_pending_approvals()
    print(f"\nPending approvals: {len(pending)}")
    for approval in pending:
        print(f"  ID: {approval['id']}, Tool: {approval['tool_name']}, Args: {approval['original_args']}")
    
    # Approve it
    if manager.approve_request(approval_id):
        print(f"\nApproved request {approval_id}")
    
    # Check status
    status = manager.get_approval_by_id(approval_id)
    print(f"\nFinal status: {status['status']}")


