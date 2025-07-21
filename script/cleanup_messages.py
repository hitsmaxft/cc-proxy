#!/usr/bin/env python3
"""
Script to cleanup incomplete messages in the database.
This script will mark all pending/incomplete messages as completed.
"""

import asyncio
import aiosqlite
import json
from datetime import datetime
from pathlib import Path

# Database path - same as used in the application
DB_PATH = "proxy.db"

async def cleanup_incomplete_messages():
    """Update all incomplete messages to completed status"""
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database file '{DB_PATH}' not found!")
        return
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # First, let's see what we're dealing with
            print("🔍 Analyzing database...")
            
            # Count messages by status
            async with db.execute("""
                SELECT status, COUNT(*) as count 
                FROM message_history 
                GROUP BY status
            """) as cursor:
                status_counts = await cursor.fetchall()
                
            print("\n📊 Current message status distribution:")
            total_messages = 0
            incomplete_count = 0
            
            for status, count in status_counts:
                print(f"   {status or 'NULL'}: {count} messages")
                total_messages += count
                if status != 'completed':
                    incomplete_count += count
            
            print(f"\n📋 Total messages: {total_messages}")
            print(f"🔄 Incomplete messages: {incomplete_count}")
            
            if incomplete_count == 0:
                print("✅ All messages are already completed!")
                return
            
            # Get details of incomplete messages
            print(f"\n🔍 Incomplete messages details:")
            async with db.execute("""
                SELECT id, request_id, timestamp, model_name, status, 
                       response_data IS NULL as missing_response,
                       input_tokens, output_tokens, total_tokens
                FROM message_history 
                WHERE status != 'completed' OR status IS NULL
                ORDER BY timestamp DESC
                LIMIT 10
            """) as cursor:
                incomplete_messages = await cursor.fetchall()
                
            for msg in incomplete_messages:
                msg_id, req_id, timestamp, model, status, missing_resp, input_tok, output_tok, total_tok = msg
                print(f"   ID {msg_id}: {model} | {status or 'NULL'} | {timestamp} | Response: {'Missing' if missing_resp else 'Present'} | Tokens: {total_tok or 0}")
            
            if len(incomplete_messages) > 10:
                print(f"   ... and {incomplete_count - 10} more")
            
            # Ask for confirmation (auto-proceed in non-interactive mode)
            print(f"\n⚠️  This will update {incomplete_count} incomplete messages to 'completed' status.")
            try:
                response = input("Continue? (y/N): ").strip().lower()
                if response != 'y':
                    print("❌ Operation cancelled.")
                    return
            except EOFError:
                # Running in non-interactive mode, proceed automatically
                print("Running in non-interactive mode, proceeding with cleanup...")
                response = 'y'
            
            # Update incomplete messages
            print(f"\n🔧 Updating {incomplete_count} incomplete messages...")
            
            # Update messages that are pending or have NULL status
            await db.execute("""
                UPDATE message_history 
                SET status = 'completed'
                WHERE status != 'completed' OR status IS NULL
            """)
            
            # For messages with missing response_data, add a placeholder
            await db.execute("""
                UPDATE message_history 
                SET response_data = '{"content": "", "stop_reason": "end_turn", "updated_by_cleanup": true}'
                WHERE response_data IS NULL OR response_data = ''
            """)
            
            # For messages with 0 or NULL tokens, try to estimate from request length
            await db.execute("""
                UPDATE message_history 
                SET 
                    input_tokens = CASE 
                        WHEN input_tokens IS NULL OR input_tokens = 0 
                        THEN COALESCE(request_length / 4, 10)
                        ELSE input_tokens 
                    END,
                    output_tokens = CASE 
                        WHEN output_tokens IS NULL OR output_tokens = 0 
                        THEN COALESCE(response_length / 4, 5)
                        ELSE output_tokens 
                    END
                WHERE (input_tokens IS NULL OR input_tokens = 0) 
                   OR (output_tokens IS NULL OR output_tokens = 0)
            """)
            
            # Update total_tokens
            await db.execute("""
                UPDATE message_history 
                SET total_tokens = COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)
                WHERE total_tokens IS NULL OR total_tokens = 0 
                   OR total_tokens != (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0))
            """)
            
            await db.commit()
            
            # Verify the changes
            print("✅ Database updated successfully!")
            
            # Show updated status distribution
            async with db.execute("""
                SELECT status, COUNT(*) as count 
                FROM message_history 
                GROUP BY status
            """) as cursor:
                new_status_counts = await cursor.fetchall()
                
            print("\n📊 Updated message status distribution:")
            for status, count in new_status_counts:
                print(f"   {status or 'NULL'}: {count} messages")
            
            # Show some statistics
            async with db.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN response_data LIKE '%updated_by_cleanup%' THEN 1 ELSE 0 END) as fixed_responses,
                    AVG(input_tokens) as avg_input,
                    AVG(output_tokens) as avg_output,
                    AVG(total_tokens) as avg_total
                FROM message_history
            """) as cursor:
                stats = await cursor.fetchone()
                
            total, fixed_responses, avg_input, avg_output, avg_total = stats
            print(f"\n📈 Database statistics:")
            print(f"   Total messages: {total}")
            print(f"   Fixed responses: {fixed_responses}")
            print(f"   Average input tokens: {avg_input:.1f}")
            print(f"   Average output tokens: {avg_output:.1f}")
            print(f"   Average total tokens: {avg_total:.1f}")
            
            print(f"\n🎉 Cleanup completed! All messages are now marked as completed.")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function"""
    print("🧹 Claude Code Proxy - Database Message Cleanup Script")
    print("=" * 60)
    
    await cleanup_incomplete_messages()
    
    print("\n" + "=" * 60)
    print("✨ Script completed!")

if __name__ == "__main__":
    asyncio.run(main())
